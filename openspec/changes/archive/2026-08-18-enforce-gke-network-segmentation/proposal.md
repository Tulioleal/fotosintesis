## Why

The repository has no Kubernetes `NetworkPolicy` resources and the GKE OpenTofu module does not enable a NetworkPolicy provider or Dataplane V2. Adding policy YAML without cluster enforcement would create a false security claim, so enforcement must be enabled first and verified with allowed/denied probes before application traffic moves to default-deny.

## What Changes

- Enable GKE Dataplane V2 (or the supported NetworkPolicy provider) explicitly in OpenTofu.
- Add namespace default-deny ingress and egress policies with narrow allow rules for the frontend, backend, worker, migrations, Cloud SQL proxy, DNS, Workload Identity, External Secrets, Managed Prometheus, and ingress health checks.
- Document how external model/search/taxonomy/evidence provider traffic is handled, without claiming FQDN-level isolation that standard NetworkPolicy cannot enforce.
- Add connectivity, denial, deployment, and rollback verification in development before production.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `gcp-deployment-platform`: Enable and operate cluster network enforcement.
- `testing-deployment`: Render, apply, and verify workload NetworkPolicies.

## Impact

- GKE OpenTofu module variables and cluster configuration.
- Kubernetes NetworkPolicy manifests and environment overlays.
- Deployment workflows with connectivity and denial checks.
- Operational documentation for enforcement enablement, troubleshooting, and rollback.
