## ADDED Requirements

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

The system SHALL include OpenTofu infrastructure code for provisioning the cloud resources required to run Fotosíntesis AI on GCP.

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
