# Network Policy Enforcement

This document is the operational reference for the
`enforce-gke-network-segmentation` change. It records how cluster enforcement
is enabled, the exact policy inventory applied to the application namespace,
how enforcement is proven, the external-provider egress limitation, and the
rollback path.

## Enforcement mechanism: GKE Dataplane V2

Kubernetes `NetworkPolicy` resources are inert without an enforcement plugin.
This cluster uses **GKE Dataplane V2** (`ADVANCED_DATAPATH`), which ships
built-in `NetworkPolicy` enforcement based on Cilium.

It is enabled explicitly in the GKE OpenTofu module:

- `infra/opentofu/modules/gke/main.tf` sets `datapath_provider =
  "ADVANCED_DATAPATH"` when `dataplane_v2 = true`.
- `infra/opentofu/modules/gke/variables.tf` declares `dataplane_v2` with a
  default of `true`.
- Both environment roots (`infra/opentofu/envs/{dev,prod}/main.tf`) pass
  `dataplane_v2 = var.dataplane_v2`; both roots default to `true`.

### Update and recreation requirements

- Enabling Dataplane V2 on an **existing** cluster recreates the node pools
  (a rolling node replacement) and can take tens of minutes. Plan for the
  disruption and respect maintenance windows.
- With Dataplane V2, network policy enforcement is built in; you cannot toggle
  the Calico `network_policy` addon on or off (`Enabling NetworkPolicy for
  clusters with DatapathProvider=ADVANCED_DATAPATH is not allowed.`), which is
  why the Terraform module deliberately omits the `network_policy` block.
- Network policy enforcement raises `kube-system` CPU/memory usage
  (approximately 300 millicores and 128 MB); existing clusters may need a
  larger node size or pool. Node types smaller than one allocatable vCPU
  (`f1-micro`, `g1-small`) are unsupported.
- Dataplane V2 never enforces policies for `spec.hostNetwork: true` Pods.

## Policy inventory

All policies live in `deploy/k8s/base/05-network-policies.yaml` and are
rendered per environment. Standard `NetworkPolicy` is additive: the
default-deny policy blocks everything, and each allow policy re-opens one
narrow path.

| Policy | Direction | Selector | Allows |
| --- | --- | --- | --- |
| `fotosintesis-default-deny` | Ingress + Egress | all Pods | nothing (catch-all deny) |
| `fotosintesis-allow-dns` | Egress | all Pods | `kube-system` DNS service TCP/UDP 53 |
| `fotosintesis-allow-workload-identity` | Egress | `iam.gke.io/workload-identity: fotosintesis-backend` | GKE metadata server `169.254.169.254:80,8080` and `169.254.169.252:988,987` |
| `fotosintesis-allow-frontend-ingress` | Ingress | frontend | GFE/health-check probe ranges on 3000 |
| `fotosintesis-allow-backend-ingress` | Ingress | backend | frontend Pods, smoke probe Pods, and Managed Prometheus (`gmp-system`) on 8000 |
| `fotosintesis-allow-worker-ingress` | Ingress | worker | Managed Prometheus (`gmp-system`) on the metrics port |
| `fotosintesis-allow-frontend-backend-egress` | Egress | frontend | backend Pods on 8000 |
| `fotosintesis-allow-smoke-egress` | Egress | smoke probe Pods | backend Pods on 8000 |
| `fotosintesis-allow-cloud-sql-proxy-egress` | Egress | Workload Identity Pods | Cloud SQL proxy outbound TCP 3307 |
| `fotosintesis-allow-external-https-egress` | Egress | all Pods | external HTTPS on TCP 443 |

### Required-traffic coverage

- **Frontend ingress / health checks**: GKE Ingress forwards requests and
  health probes from the documented Application Load Balancer probe ranges
  (`35.191.0.0/16`, `130.211.0.0/22`, `209.85.152.0/22`, `209.85.204.0/22`).
  The frontend Service carries the `cloud.google.com/neg: '{"ingress": true}'`
  annotation so container-native load balancing is retained under network
  policy (GKE stops adding it automatically once enforcement is enabled);
  without it, traffic would arrive from node IPs and the policy could not
  express the source narrowly.
- **Frontend to backend**: the Next.js server reaches the backend through the
  in-cluster Service. DNS egress (all Pods) plus frontend egress to the
  backend (port 8000) and backend ingress from the frontend cover it.
- **Backend/worker/migrations/limiter-cleanup to Cloud SQL**: the Cloud SQL
  Auth Proxy runs as a sidecar/init container in the same Pod, so database
  traffic stays on loopback and needs no policy. The proxy's outbound
  connection to the Cloud SQL instance proxy port (3307) is covered by
  `fotosintesis-allow-cloud-sql-proxy-egress`.
- **Workload Identity**: token requests to the GKE metadata server are covered
  by `fotosintesis-allow-workload-identity`. GCS, Secret Manager and Cloud
  Monitoring calls authenticate with these tokens over HTTPS and are covered by
  the external HTTPS egress.
- **External Secrets Operator**: ESO runs in the `external-secrets` namespace
  and reconciles the namespace `SecretStore`/`ExternalSecret` objects through
  the control plane. It has no Pods in the application namespace, so the
  namespace default-deny does not affect it.
- **Managed Prometheus**: the collector in `gmp-system` scrapes backend
  (8000 `/metrics`) and worker (metrics port `/metrics`) through the ingress
  allow rules from the `gmp-system` namespace.
- **Smoke checks**: the deploy in-cluster smoke probe Pod and the
  network-policy verification probe Pod carry the
  `app.kubernetes.io/name: fotosintesis-smoke` label; DNS egress and smoke
  egress to the backend allow them to run the `/health` check.

## Verification

Policy YAML presence is not proof of enforcement. Two layers verify the
baseline:

### Rendered-manifest validation (CI, offline)

`backend/scripts/validate_rendered_manifests.py` validates every rendered
directory. Its `validate_network_policies` checks confirm that:

- the namespace default-deny policy exists, covers the whole namespace
  (`podSelector: {}`), declares both `Ingress` and `Egress`, and carries no
  allow rules;
- every in-namespace `podSelector` used by a policy matches at least one
  deployed workload's Pod template labels (or a documented runtime probe
  label such as `fotosintesis-smoke`); and
- each required allow rule is present (DNS, metadata server, frontend ingress
  from GFE ranges, backend ingress from frontend and `gmp-system`, worker
  ingress from `gmp-system`, frontend and smoke egress to the backend, Cloud
  SQL proxy egress, external HTTPS egress).

This runs as part of the `backend` test suite
(`backend/tests/deployment/test_render_network_policy.py`) for both the dev
and prod values files.

### Connectivity probes (live, development)

`deploy.yml` runs `deploy/scripts/verify-network-policy.sh` for the **dev**
environment after the rollouts. The script proves real enforcement:

1. An **allowed** probe Pod (labelled `fotosintesis-smoke`) curls the backend
   `/health` endpoint and **must succeed**.
2. A **denied** probe Pod (no allow labels) curls the same endpoint and
   **must fail**; under default-deny its egress to the backend is blocked.

The result is recorded in the deploy summary as "Network policy verification".
Run the same script manually against any environment to re-prove enforcement.

## External-provider egress limitation

Standard `NetworkPolicy` cannot express portable hostname/FQDN allowlists.
Model, search, taxonomy, and evidence providers (OpenAI, Gemini, evidence
fetching) therefore use the documented bounded egress
`fotosintesis-allow-external-https-egress`: TCP 443 to `0.0.0.0/0`.

Two GKE Dataplane V2 behaviors bound this rule:

- An `ipBlock` rule **never** covers Pod traffic with Dataplane V2, so
  `0.0.0.0/0` reaches external endpoints only, not other Pods. This is not the
  case under Calico, where the Pod CIDR would need an explicit `except`.
- The Cloud SQL proxy egress (TCP 3307 to `0.0.0.0/0`) exists for the same
  reason: the SQL instance endpoint is dynamic and cannot be allow-listed by
  hostname.

This is **HTTPS-bounded, not FQDN-isolated**. Any Pod that is authorized to
reach external endpoints can reach any external HTTPS host. Do not document or
treat this as hostname-level isolation. If FQDN-level egress control is
required later, GKE FQDN network policies are the supported mechanism, not
standard `NetworkPolicy`.

Dataplane V2 does not honor the `endPort` field on ports below GKE 1.32, so
the policies use single ports only.

## Troubleshooting

Start with the deploy summary: "Network policy verification (dev)" must report
`pass`, and the migration/rollout/smoke rows must be `pass`.

- **Denied probe does not fail** (allow everything is still open): confirm the
  cluster actually runs Dataplane V2
  (`kubectl -n kube-system get pods -l k8s-app=cilium -o wide`; expect `anetd-*`
  Pods), then confirm the policies are applied
  (`kubectl -n <namespace> get networkpolicies`).
- **Allowed probe / smoke check fails after enabling policies**: confirm the
  allow rules cover the path. DNS failures point at the CoreDNS egress rule;
  Cloud SQL failures at the proxy egress (3307); token/authorization failures
  at the metadata-server egress; auth failures against GCS/Secret Manager at
  the HTTPS egress. Check `anetd` logs
  (`kubectl -n kube-system logs daemonset/anetd`), enable network-policy deny
  logging on the namespace, and review Cloud Logging `policy-action` entries.
- **Ingress health checks keep failing**: confirm the frontend Service keeps
  the NEG annotation and the frontend ingress rule lists the probe ranges.
- **Readiness/liveness probes fail under default-deny**: kubelet probes
  originate from the node and are not sourced from a Pod. If a future GKE
  version applies policies to them, add an ingress allow rule from the node
  CIDR to the affected ports before default-deny.
- **DNS does not resolve for newly created transient Pods**: the DNS allow rule
  permits TCP/UDP 53 to the `kube-system` namespace. Verify the policy is
  applied and inspect `anetd` logs for denied DNS traffic.

## Rollback

Two independent rollback paths restore previous connectivity; they are
documented here and should be exercised in development before promotion.

### Remove the policies (fast, no node churn)

Deleting the `NetworkPolicy` resources restores default Kubernetes behavior
(allow all) without any cluster change:

```bash
kubectl delete -f ".generated/k8s/$ENVIRONMENT/rendered/05-network-policies.yaml" \
  --ignore-not-found
```

Reapply with `kubectl apply -f ".generated/k8s/$ENVIRONMENT/rendered/05-network-policies.yaml"`
once the disruption is understood. Because `deploy.yml` applies the policies
on every deploy, a permanent removal also requires removing the file from
`deploy/k8s/base/` and the corresponding step in `deploy.yml`.

### Disable cluster enforcement (heavy, node recreation)

Setting `dataplane_v2 = false` in the environment root
(`infra/opentofu/envs/{dev,prod}`), applying, then reverting the removal is
the full rollback. Disabling or changing the datapath provider recreates the
node pools; with a maintenance window configured, nodes are recreated at the
next window. Re-run `tofu plan` before applying any rollback change. This is
the last resort: removing policies is always faster and sufficient to restore
connectivity.
