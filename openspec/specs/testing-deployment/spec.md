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
- **THEN** they define frontend, backend and required supporting resources with configurable environment values, including runtime config, Workload Identity service accounts, External Secrets references, Cloud SQL proxy configuration, migration execution, and frontend ingress resources

### Requirement: Setup and operations documentation

The system SHALL document local setup, environment variables, mocks, provider configuration, evaluation run and deployment path.

#### Scenario: New developer follows setup docs

- **WHEN** a developer follows the documented local setup
- **THEN** they can run the stack with mocks and understand how to configure real providers later

### Requirement: Infrastructure as Code provisioning

The system SHALL include OpenTofu infrastructure code for provisioning the bootstrap foundation, cloud resources, runtime workload identity, and deployment outputs required to run Fotosintesis AI on GCP.

#### Scenario: Infrastructure plan is generated

- **WHEN** a developer runs the documented `tofu plan` command
- **THEN** OpenTofu produces plans for the local-only bootstrap root and the dev/prod environment roots, with bootstrap managing remote state, API enablement, GitHub OIDC, CI/deploy identities and state-bucket IAM, while environment roots manage GKE, Artifact Registry, Cloud SQL for PostgreSQL, application Cloud Storage, Secret Manager containers, runtime IAM, frontend static IP, deployment outputs and baseline monitoring resources without requiring application source changes.

#### Scenario: Infrastructure is applied

- **WHEN** a developer runs the documented `tofu apply` command with valid variables and credentials
- **THEN** the required cloud infrastructure is created or updated reproducibly.

#### Scenario: Bootstrap root is applied before environment roots

- **WHEN** a new environment is initialized
- **THEN** the documented flow applies the local-only bootstrap root first, migrates bootstrap state to its GCS backend, configures GitHub variables from bootstrap outputs, and only then applies dev/prod environment roots against the bootstrap-created state buckets

#### Scenario: Deployment consumes IaC outputs

- **WHEN** the Kubernetes deployment is applied
- **THEN** it consumes OpenTofu outputs for cluster, image registry, database, storage, secret references, Workload Identity service accounts and frontend ingress static IP values instead of hardcoded cloud values.

#### Scenario: Bootstrap-owned resources are not duplicated

- **WHEN** infrastructure code is inspected or validated
- **THEN** project API enablement, remote state buckets, GitHub OIDC providers, CI/deploy service accounts, CI/deploy IAM and GitHub principalSet bindings are owned only by the bootstrap root, not by dev/prod environment roots.

#### Scenario: Secrets remain outside source control

- **WHEN** infrastructure and deployment files are inspected
- **THEN** provider keys, database passwords, session secrets and API tokens are not committed to the repository.

#### Scenario: Infrastructure can be destroyed

- **WHEN** a developer runs the documented `tofu destroy` command for a non-production environment
- **THEN** the managed cloud resources are removed according to documented safeguards.

### Requirement: Plain Kubernetes deployment artifacts

The system SHALL use plain Kubernetes manifests, not Helm, for application workload deployment onto GKE while cloud infrastructure provisioning remains managed by OpenTofu.

#### Scenario: Deployment artifacts reviewed

- **WHEN** deployment artifacts are inspected
- **THEN** they define plain Kubernetes manifests for namespace, frontend Deployment and Service, backend Deployment and Service, migration Job, Kubernetes service accounts for Workload Identity, required runtime configuration references, ExternalSecret resources, Cloud SQL proxy configuration and frontend ingress resources

#### Scenario: Helm is not required for app workloads

- **WHEN** a developer follows the documented deployment path
- **THEN** no Helm chart is required to deploy the Fotosintesis application workloads

### Requirement: Deployment consumes OpenTofu outputs

The Kubernetes deployment SHALL consume environment-specific values derived from OpenTofu outputs instead of hardcoded cloud project values.

#### Scenario: Runtime values are configured from infrastructure outputs

- **WHEN** the Kubernetes manifests are prepared for an environment
- **THEN** image registry, GKE cluster details, Workload Identity service account emails, object storage bucket, database connection information, frontend static IP information and secret references are populated from documented OpenTofu outputs or an environment-specific values file generated from those outputs

#### Scenario: Cloud project values are not hardcoded

- **WHEN** deployment manifests are inspected
- **THEN** they avoid hardcoded cloud project identifiers, provider credentials, database passwords, session secrets and API tokens

### Requirement: Kubernetes deployment operations documentation

The system SHALL document deployment, verification, rollback and cleanup using GitHub Actions, `kubectl` and OpenTofu without requiring application Helm charts.

#### Scenario: Deployment is applied

- **WHEN** a developer follows the deployment documentation
- **THEN** they can understand how GitHub Actions renders environment-specific deployment values from `tofu output`, applies manifests, waits for migrations, checks frontend and backend rollout status, and runs smoke checks

#### Scenario: Rollback is documented

- **WHEN** a deployed workload must be reverted
- **THEN** the documentation provides image tag redeploy guidance, `kubectl rollout undo` guidance for frontend and backend Deployments, and migration rollback guidance that relies on backup restore or reviewed forward-fix migrations rather than Helm rollback

#### Scenario: Environment is cleaned up

- **WHEN** a developer follows cleanup documentation for a non-production environment
- **THEN** they can remove Kubernetes resources with `kubectl delete` and destroy managed cloud resources with `tofu destroy` according to documented safeguards

### Requirement: Secret examples remain non-applied

The deployment artifacts SHALL keep real secrets out of source control and SHALL NOT place example Secret values in rendered deployment paths that are intended to be applied directly.

#### Scenario: Secret handling is reviewed

- **WHEN** deployment files are inspected
- **THEN** any example Secret is outside applied manifest directories or clearly documented as a non-applied example, runtime manifests reference secret names without committing secret values, and ExternalSecret resources refer to Secret Manager keys rather than embedding secret values

### Requirement: GitHub Actions deployment automation
The system SHALL provide GitHub Actions workflows for backend CI, frontend CI, OpenTofu infrastructure, environment deployment, and production release promotion.

#### Scenario: Workflow set is present
- **WHEN** deployment automation files are inspected
- **THEN** the repository includes workflows for backend validation/build, frontend validation/build, OpenTofu plan/apply, Kubernetes deployment, and production release promotion

#### Scenario: Dev deployment follows successful main builds
- **WHEN** backend or frontend image builds succeed on `main`
- **THEN** the relevant workflow triggers or calls the dev deployment flow with immutable Git SHA image tags

### Requirement: HTTPS frontend ingress
The system SHALL expose the frontend through GKE HTTPS Ingress using a reserved static IP and managed certificate configuration.

#### Scenario: Frontend ingress is rendered
- **WHEN** Kubernetes manifests are rendered for an environment with a public frontend host
- **THEN** the rendered resources include frontend Ingress, managed certificate configuration, and static IP reference values for that environment

#### Scenario: DNS setup is documented
- **WHEN** deployment documentation is inspected
- **THEN** it explains that DNS must point the configured hostname to the reserved static IP before HTTPS smoke checks can pass in `hostname-https` mode, and that `ip-http` mode uses direct HTTP access through the reserved static IP

### Requirement: External Secrets runtime secret projection
The system SHALL use External Secrets Operator to project GCP Secret Manager secret values into Kubernetes runtime secrets.

#### Scenario: External secret resources are rendered
- **WHEN** Kubernetes manifests are rendered for an environment
- **THEN** they include SecretStore or ClusterSecretStore configuration and ExternalSecret resources that map required Secret Manager values to the runtime Kubernetes Secret name consumed by workloads

#### Scenario: Secret values are not committed
- **WHEN** deployment manifests, OpenTofu files, workflow files, and docs are inspected
- **THEN** they do not include provider API keys, database passwords, session secrets, or other secret values

### Requirement: Cloud SQL proxy workload connectivity
The system SHALL run backend and migration workloads with Cloud SQL Auth Proxy connectivity to the environment Cloud SQL instance.

#### Scenario: Backend includes Cloud SQL proxy
- **WHEN** backend Kubernetes manifests are rendered for GCP deployment
- **THEN** the backend pod specification includes Cloud SQL Auth Proxy configuration using the environment Cloud SQL instance connection name and Workload Identity service account

#### Scenario: Migration job includes Cloud SQL proxy
- **WHEN** migration Job manifests are rendered for GCP deployment
- **THEN** the migration pod can connect to the same Cloud SQL instance through Cloud SQL Auth Proxy before running Alembic migrations

### Requirement: Authentication dependency security gate

Frontend CI SHALL verify the installed frozen-lockfile Auth.js dependency shape and SHALL scan production dependencies for high-severity advisories before build or deployment.

#### Scenario: Patched aligned dependency graph is verified

- **WHEN** frontend CI installs dependencies with the frozen lockfile
- **THEN** a deterministic policy check verifies exact `next-auth@5.0.0-beta.32`, no direct `@auth/core`, one reachable transitive core version, and no direct core imports
- **AND** the production dependency advisory scan reports no GHSA-8fpg-xm3f-6cx3 finding

#### Scenario: Authentication dependency policy is violated

- **WHEN** the manifest, installed graph, source imports, or advisory scan contains an affected or unaligned Auth.js dependency
- **THEN** frontend CI fails before image build or deployment

#### Scenario: Root dependency files change

- **WHEN** a pull request or main-branch push changes the root package manifest, pnpm lockfile, or pnpm workspace definition
- **THEN** the frontend validation workflow runs the authentication dependency security gate

### Requirement: Authentication upgrade regression gate

The Auth.js security upgrade SHALL pass focused fail-closed tests and the existing complete frontend validation and authentication journey before deployment.

#### Scenario: Authentication release candidate is verified

- **WHEN** the upgraded frontend is prepared for merge
- **THEN** focused tests cover missing configuration, decode failure, malformed credentials responses, stale backend sessions, credential non-exposure, callback routing, and logout
- **AND** lint, typecheck, full component tests, generated contract verification, production build, and authentication end-to-end tests pass

#### Scenario: Production server starts without Auth.js secrets

- **WHEN** CI starts the built frontend on an isolated local port with both supported Auth.js secret variables removed
- **THEN** a representative private-route request redirects to `/login`
- **AND** the smoke fails if private content or a successful authorization result is returned
- **AND** the production server is terminated after the bounded check

### Requirement: Authentication limiter verification

The system SHALL include automated tests that verify authentication limit response contracts, privacy properties, storage-failure policies, atomic concurrency bounds, and distributed enforcement.

#### Scenario: Backend limiter tests run

- **WHEN** backend unit and PostgreSQL integration tests run
- **THEN** they verify endpoint thresholds, atomic concurrent updates, expiry cleanup, successful-login relaxation, safe storage-failure behavior, and equivalent known-versus-unknown recovery outcomes

#### Scenario: Frontend limiter tests run

- **WHEN** frontend component and authentication journey tests run
- **THEN** they verify `429` and `Retry-After` propagation, bounded retry presentation, disabled resubmission, and neutral recovery copy

#### Scenario: Multi-replica verification runs

- **WHEN** the deployment verification sends matching invalid credential attempts through at least two application instances
- **THEN** their combined allowed attempts do not exceed the configured shared limit

### Requirement: Authentication limiter deployment contract

The Kubernetes deployment SHALL configure documented authentication limit profiles, keyed-digest secrets, trusted proxy behavior, retention, and endpoint-specific storage-failure policies consistently across replicas without committing secret values.

#### Scenario: Deployment artifacts are rendered

- **WHEN** authentication limiter deployment configuration is rendered for an environment
- **THEN** every relevant frontend and backend replica receives compatible non-secret policy settings
- **AND** keyed-digest material is projected from the runtime secret mechanism

#### Scenario: Limiter metrics are scraped

- **WHEN** authentication abuse metrics are emitted by application replicas
- **THEN** existing monitoring discovers the metrics with only closed endpoint-category and outcome labels

### Requirement: Trusted proxy deployment verification

The deployment SHALL document and test the exact GKE ingress-to-frontend trust chain used for source identity and SHALL apply a conservative identity when that chain cannot be established.

#### Scenario: Forwarding header spoofing is tested

- **WHEN** deployment verification sends requests with spoofed forwarding-header entries
- **THEN** the application ignores untrusted entries and does not create attacker-selected limiter identities

### Requirement: Edge protection remains complementary

Any Cloud Armor or equivalent volumetric rate limit SHALL be configured and documented as a separate optional edge control and MUST NOT replace application account-aware authentication limits.

#### Scenario: Edge protection is absent or changed

- **WHEN** no edge rate-limit policy is enabled or its threshold changes
- **THEN** distributed application source-aware and account-aware authentication limits remain enforced
