## ADDED Requirements

### Requirement: Plain Kubernetes deployment artifacts

The system SHALL use plain Kubernetes manifests, not Helm, for MVP application workload deployment onto GKE while cloud infrastructure provisioning remains managed by OpenTofu.

#### Scenario: Deployment artifacts reviewed

- **WHEN** deployment artifacts are inspected
- **THEN** they define plain Kubernetes manifests for namespace, frontend Deployment and Service, backend Deployment and Service, migration Job, Kubernetes service accounts for Workload Identity and required runtime configuration references

#### Scenario: Helm is not required

- **WHEN** a developer follows the documented deployment path
- **THEN** no `helm` CLI command or Helm chart is required to deploy the MVP workloads

### Requirement: Deployment consumes OpenTofu outputs

The Kubernetes deployment SHALL consume environment-specific values derived from OpenTofu outputs instead of hardcoded cloud project values.

#### Scenario: Runtime values are configured from infrastructure outputs

- **WHEN** the Kubernetes manifests are prepared for an environment
- **THEN** image registry, GKE or Workload Identity service account emails, object storage bucket, database connection information and secret references are populated from documented OpenTofu outputs or an environment-specific values file generated from those outputs

#### Scenario: Cloud project values are not hardcoded

- **WHEN** deployment manifests are inspected
- **THEN** they avoid hardcoded cloud project identifiers, provider credentials, database passwords, session secrets and API tokens

### Requirement: Kubernetes deployment operations documentation

The system SHALL document deployment, verification, rollback and cleanup using `kubectl` and OpenTofu without requiring Helm.

#### Scenario: Deployment is applied

- **WHEN** a developer follows the deployment documentation
- **THEN** they can generate or fill environment-specific deployment values from `tofu output`, apply manifests with `kubectl apply` and check frontend and backend rollout status

#### Scenario: Rollback is documented

- **WHEN** a deployed workload must be reverted
- **THEN** the documentation provides `kubectl rollout undo` guidance for frontend and backend Deployments plus migration/job rollback guidance that does not depend on Helm rollback

#### Scenario: Environment is cleaned up

- **WHEN** a developer follows cleanup documentation for a non-production environment
- **THEN** they can remove Kubernetes resources with `kubectl delete` and destroy managed cloud resources with `tofu destroy` according to documented safeguards

### Requirement: Secret examples remain non-applied

The deployment artifacts SHALL keep real secrets out of source control and SHALL NOT place example Secret values in rendered deployment paths that are intended to be applied directly.

#### Scenario: Secret handling is reviewed

- **WHEN** deployment files are inspected
- **THEN** any example Secret is outside applied manifest directories or clearly documented as a non-applied example, and runtime manifests reference secret names without committing secret values
