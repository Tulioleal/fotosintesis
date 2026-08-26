## Context

The cluster currently runs with no Kubernetes `NetworkPolicy` and no enforcement provider. This change enables enforcement at the cluster level, then applies default-deny namespaces with explicit allow rules so segmentation is real rather than cosmetic.

## Goals / Non-Goals

**Goals:**

- Enable a supported enforcement mechanism explicitly in the GKE OpenTofu module.
- Prove enforcement with one allowed and one denied probe in development.
- Default-deny ingress/egress per application namespace with narrow allow rules.
- Keep DNS, Cloud SQL, Workload Identity, External Secrets, Managed Prometheus, ingress health checks, and smoke checks working.
- Document external-provider egress honestly.

**Non-Goals:**

- No service mesh.
- No FQDN-level filtering via standard NetworkPolicy.
- No changes to application authentication or authorization.
- No private VPC connectivity for every external provider.

## Decisions

- **Enforcement mechanism: GKE Dataplane V2.** Enabled via `dataplane_v2 = true` on the cluster module. It requires no extra addon, is the supported default, and works with standard `NetworkPolicy`. Alternative (Calico) rejected as more moving parts for no benefit here.
- **Policy baseline: namespace default-deny.** Each application namespace gets a catch-all `NetworkPolicy` denying ingress and egress, with targeted `allow` policies layered on top.
- **Allow rules by workload.** Frontend accepts ingress from the load balancer/health checks and egress to backend; backend/worker/migration accept ingress from frontend and smoke pods, and egress to DNS, Cloud SQL proxy, Workload Identity/metadata, Secret Manager, and Managed Prometheus. Metrics scraping is allowed from the monitoring namespace.
- **External providers: broad HTTPS egress.** Standard NetworkPolicy cannot express portable FQDN allowlists, so external model/search/taxonomy/evidence traffic uses an `ipBlock: 0.0.0.0/0` allow on TCP 443 with documentation that this is bounded to HTTPS, not hostname-level isolation.
- **Rollback: disable enforcement or delete policies.** Before enabling, document how to set `dataplane_v2 = false` (recreate if required) or delete the NetworkPolicy resources to restore previous connectivity.

## Risks / Trade-offs

- [Enabling enforcement disrupts existing traffic] → Inventory and probe all dependencies in development first; apply default-deny only after allow rules are in place.
- [Existing clusters may require recreation for Dataplane V2] → Document the update path and rollback before applying infrastructure changes.
- [Dynamic provider endpoints defeat static allowlists] → Document the bounded HTTPS compromise and monitor; do not claim FQDN isolation.
- [Policy YAML drifts from pod labels] → Rendered-manifest tests validate selector labels match deployed workloads.

## Migration Plan

1. Enable Dataplane V2 in development and verify cluster health.
2. Prove a denied probe fails and an allowed probe succeeds.
3. Add explicit allow policies, then default-deny, and run smoke/observability checks.
4. Promote to production with rollback prepared and documented.
