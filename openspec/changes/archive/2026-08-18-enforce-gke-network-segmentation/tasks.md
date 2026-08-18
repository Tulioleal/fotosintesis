## 1. Enable Cluster Enforcement

- [x] 1.1 Add explicit Dataplane V2 (or supported provider) configuration to the GKE OpenTofu module and document the enablement and any in-place update or recreation requirement.

## 2. Apply Namespace Policies

- [x] 2.1 Add default-deny ingress and egress NetworkPolicies for each application namespace.
- [x] 2.2 Add narrow allow policies for frontend, backend, worker, migrations, Cloud SQL proxy, DNS, Workload Identity, External Secrets, Managed Prometheus, and ingress health checks.
- [x] 2.3 Add the documented bounded HTTPS egress policy for external providers.

## 3. Verification

- [x] 3.1 Add rendered-manifest validation that NetworkPolicy selectors match deployed workloads.
- [x] 3.2 Add connectivity verification proving an allowed probe succeeds and a denied probe fails in development.
- [x] 3.3 Verify frontend, backend, worker, migrations, DNS, Cloud SQL, Workload Identity, External Secrets, Managed Prometheus, ingress health, and smoke checks still pass.

## 4. Operations

- [x] 4.1 Document the rollback path (disable enforcement or remove policies) and exercise it in development.
- [x] 4.2 Document external-provider egress limitations and troubleshooting.
