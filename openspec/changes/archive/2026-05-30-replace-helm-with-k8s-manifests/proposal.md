## Why

The current deployment implementation uses a Helm chart even though the OpenSpec requirement only needs deployable Kubernetes/GKE artifacts. For the MVP, static Kubernetes manifests reduce tooling, review surface and operational complexity while still satisfying the deployment and IaC-output requirements.

## What Changes

- Replace the Helm chart under `deploy/helm/fotosintesis` with plain Kubernetes manifests under `deploy/k8s`.
- Add base manifests and environment-specific overlays or documented placeholder substitution for namespace, frontend, backend, migration job, Kubernetes service accounts for Workload Identity and runtime config references.
- Update deployment and rollback documentation to use `kubectl apply`, `kubectl rollout status`, `kubectl rollout undo`, migration/job guidance and cleanup steps instead of Helm commands.
- Remove Helm from deployment prerequisites and verification instructions.
- Keep cloud infrastructure provisioning in `infra/opentofu` and ensure Kubernetes deployment inputs are sourced from OpenTofu outputs rather than hardcoded cloud project values.
- Keep real secrets out of source control; any example Secret must live outside rendered deployment paths or be clearly documented as non-applied example material.

## Capabilities

### New Capabilities

- `testing-deployment`: narrows the MVP deployment artifact requirement to plain Kubernetes manifests and documents how they consume OpenTofu outputs without Helm.

### Modified Capabilities

- None.

## Impact

- Affects deployment manifests, deployment documentation, rollback documentation and verification guidance.
- Removes Helm as a required operator dependency for MVP deployment.
- Does not change OpenTofu-managed cloud infrastructure, application APIs, runtime behavior or secret-storage policy.
