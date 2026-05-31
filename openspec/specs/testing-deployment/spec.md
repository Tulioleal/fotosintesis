## Purpose

Define MVP testing, deployment and operational documentation requirements for Fotosintesis AI.

## Requirements

### Requirement: Backend tests

The system SHALL include backend unit and integration tests for core MVP domains and API endpoints.

#### Scenario: Backend tests run locally

- **WHEN** the documented backend test command runs
- **THEN** it executes unit and integration coverage using mocks where real providers are unavailable

### Requirement: Frontend tests

The system SHALL include frontend component tests for critical forms, screens and UI states.

#### Scenario: Component tests run locally

- **WHEN** the documented frontend component test command runs
- **THEN** it verifies forms, Home, candidate selection, profile, garden, reminders and light meter states

### Requirement: End-to-end tests

The system SHALL include Playwright tests for primary MVP journeys and fallback flows.

#### Scenario: E2E suite runs

- **WHEN** the Playwright suite runs against the local stack
- **THEN** it verifies auth, Home navigation, identification to profile, garden save, reminder creation, assistant RAG and light fallback

### Requirement: Deployment artifacts

The system SHALL include Kubernetes/GKE manifests for frontend, backend and runtime workloads, while cloud infrastructure provisioning is handled by OpenTofu.

#### Scenario: Deployment manifests reviewed

- **WHEN** deployment artifacts are inspected
- **THEN** they define frontend, backend and required supporting resources with configurable environment values

### Requirement: Setup and operations documentation

The system SHALL document local setup, environment variables, mocks, provider configuration, evaluation run and deployment path.

#### Scenario: New developer follows setup docs

- **WHEN** a developer follows the documented local setup
- **THEN** they can run the stack with mocks and understand how to configure real providers later

### Requirement: Infrastructure as Code provisioning

The system SHALL include OpenTofu infrastructure code for provisioning the cloud resources required to run Fotosintesis AI on GCP.

#### Scenario: Infrastructure plan is generated

- **WHEN** a developer runs the documented `tofu plan` command
- **THEN** OpenTofu produces a plan for GKE, Artifact Registry, Cloud SQL for PostgreSQL, Cloud Storage, Secret Manager, IAM and baseline monitoring resources without requiring application source changes.

#### Scenario: Infrastructure is applied

- **WHEN** a developer runs the documented `tofu apply` command with valid variables and credentials
- **THEN** the required cloud infrastructure is created or updated reproducibly.

#### Scenario: Deployment consumes IaC outputs

- **WHEN** the Kubernetes deployment is applied
- **THEN** it consumes OpenTofu outputs for cluster, image registry, database, storage and secret references instead of hardcoded cloud values.

#### Scenario: Secrets remain outside source control

- **WHEN** infrastructure and deployment files are inspected
- **THEN** provider keys, database passwords, session secrets and API tokens are not committed to the repository.

#### Scenario: Infrastructure can be destroyed

- **WHEN** a developer runs the documented `tofu destroy` command for a non-production environment
- **THEN** the managed cloud resources are removed according to documented safeguards.

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
