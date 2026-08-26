## ADDED Requirements

### Requirement: Durable background worker deployment

The GCP runtime SHALL deploy the durable background worker as a long-running Kubernetes Deployment separate from the backend API and migration Job, using the same immutable backend image version and compatible runtime configuration.

#### Scenario: Worker is deployed with backend release
- **WHEN** deployment manifests are rendered for a release that enables durable jobs
- **THEN** they include a worker Deployment using the same 40-character backend Git commit SHA image as the API
- **AND** the worker runs the dedicated worker entrypoint rather than Uvicorn or the migration command

#### Scenario: Worker uses runtime dependencies
- **WHEN** the worker starts in GKE
- **THEN** it uses the backend workload identity, database connectivity, runtime secrets, provider configuration, and resource limits required by registered handlers
- **AND** it does not expose a public Kubernetes Service

#### Scenario: Migration Job remains separate
- **WHEN** deployment applies database migrations and worker manifests
- **THEN** the one-shot migration Job completes before the new worker rollout is considered ready
- **AND** the migration Job is not reused as a long-running job consumer

### Requirement: Worker deployment verification

Deployment and release workflows SHALL verify the worker Deployment rollout when durable background jobs are enabled.

#### Scenario: Worker rollout succeeds
- **WHEN** the worker manifest is applied during deployment
- **THEN** the deployment workflow waits for the worker Deployment rollout before reporting success

#### Scenario: Worker rollout fails
- **WHEN** the worker cannot start, connect to required runtime dependencies, or reach its desired replica state
- **THEN** the deployment workflow reports failure and does not present the release as fully successful

### Requirement: Local worker operation

The project SHALL document and provide a reproducible command for running the durable worker separately from the API in local development.

#### Scenario: Developer runs worker locally
- **WHEN** a developer starts the documented worker command with valid local configuration
- **THEN** the worker uses the same PostgreSQL-backed job contracts and handler registry as the deployed runtime
