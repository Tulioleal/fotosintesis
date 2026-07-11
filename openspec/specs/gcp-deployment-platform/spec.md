## Purpose

Define the GCP deployment platform, CI/CD foundation, release controls, and verification requirements for Fotosintesis AI.

## Requirements

### Requirement: Path-scoped CI/CD workflows
The system SHALL provide GitHub Actions workflows that run backend, frontend, infrastructure, deployment, and release jobs according to the changed repository paths and explicit operator dispatches.

#### Scenario: Backend changes run backend workflow
- **WHEN** a pull request or merge changes backend source, backend tests, backend dependency metadata, or the backend Dockerfile
- **THEN** the backend workflow validates the backend and does not require unrelated frontend or OpenTofu jobs to run as part of that path trigger

#### Scenario: Frontend changes run frontend workflow
- **WHEN** a pull request or merge changes frontend source, frontend tests, frontend dependency metadata, or the frontend Dockerfile
- **THEN** the frontend workflow validates the frontend and does not require unrelated backend or OpenTofu jobs to run as part of that path trigger

#### Scenario: Infrastructure changes run OpenTofu workflow
- **WHEN** a pull request or merge changes `infra/opentofu/**`
- **THEN** the OpenTofu workflow runs format, initialization, validation, and plan checks for the affected environment scope

### Requirement: OIDC-based GCP authentication
GitHub Actions jobs that interact with GCP SHALL authenticate through GitHub OIDC and GCP Workload Identity Federation instead of committed credentials or long-lived service account keys.

#### Scenario: Workflow requests OIDC token
- **WHEN** a workflow needs to call GCP APIs, push images, read OpenTofu outputs, or deploy to GKE
- **THEN** the workflow declares `id-token: write` and authenticates to the configured GCP service account through the Workload Identity provider

#### Scenario: Service account keys are absent
- **WHEN** repository workflow files and deployment documentation are inspected
- **THEN** they do not require storing GCP service account JSON keys in GitHub secrets or source control

### Requirement: Bootstrap-owned deployment foundation
The system SHALL provide a local-only OpenTofu bootstrap root that creates and owns deployment foundation resources needed before dev/prod environment roots can be planned or applied from GitHub Actions.

#### Scenario: Bootstrap creates remote state foundation
- **WHEN** the bootstrap root is applied by an operator with administrator credentials
- **THEN** it creates separate dev/prod environment state buckets with versioning, uniform bucket-level access, configurable names, and documented backend prefixes

#### Scenario: Bootstrap state remains local
- **WHEN** the bootstrap root is applied by an operator
- **THEN** its state remains on the operator workstation because the bootstrap root has no backend block or bootstrap state bucket

#### Scenario: Bootstrap grants state bucket access by responsibility
- **WHEN** bootstrap configures IAM for state buckets
- **THEN** environment CI service accounts receive read/write access to their environment state buckets, deploy service accounts receive read-only access needed to read OpenTofu outputs, and configured `bootstrap_admin_members` receive administrative recovery access

#### Scenario: Bootstrap owns project API enablement
- **WHEN** dev and prod project APIs are configured
- **THEN** bootstrap, not the dev/prod environment roots, manages required API enablement for GKE, Artifact Registry, Cloud SQL, Secret Manager, IAM, IAM Credentials, Storage, Monitoring, Compute, and Cloud Resource Manager

#### Scenario: Bootstrap owns GitHub OIDC and workflow identities
- **WHEN** GitHub Actions authenticate to GCP
- **THEN** per-project Workload Identity pools/providers, CI, deploy, and IaC service accounts, their project IAM, and GitHub principalSet impersonation bindings are owned by bootstrap outputs and not by dev/prod environment roots

#### Scenario: Bootstrap publishes foundation variables
- **WHEN** bootstrap is applied with a GitHub token authorized to manage Actions variables
- **THEN** it publishes non-secret, environment-scoped foundation identifiers to GitHub repository variables without writing runtime secret values

#### Scenario: Bootstrap remains local-only
- **WHEN** repository workflows are inspected
- **THEN** no GitHub Actions workflow applies the bootstrap root, because bootstrap owns the OIDC and state foundation those workflows depend on

### Requirement: Environment roots exclude bootstrap-owned resources
The dev and prod OpenTofu environment roots SHALL manage runtime infrastructure only and SHALL NOT duplicate ownership of resources owned by the bootstrap root.

#### Scenario: Runtime infrastructure remains in environment roots
- **WHEN** dev/prod environment roots are inspected
- **THEN** they continue to manage runtime resources such as Artifact Registry, GKE, Cloud SQL, application object storage, Secret Manager containers, frontend static IP, monitoring, runtime workload service accounts, runtime IAM, and deployment outputs

#### Scenario: Foundation resources are removed from environment roots
- **WHEN** dev/prod environment roots are inspected
- **THEN** they do not call project-service enablement modules, create GitHub Workload Identity providers, create CI/deploy/IaC service accounts, bind GitHub principalSets to service accounts, create remote state buckets, or output bootstrap-owned values

#### Scenario: Cleanup checks verify single ownership
- **WHEN** implementation validation runs before live deployment
- **THEN** lightweight checks verify that bootstrap-owned resources no longer appear in dev/prod environment roots while runtime IAM remains available through a focused runtime IAM module

### Requirement: Environment-isolated GCP deployment
The system SHALL treat dev and prod as separate GCP project deployments with separate state, Artifact Registry repositories, runtime resources, and CI/CD identities.

#### Scenario: Dev and prod use separate project values
- **WHEN** OpenTofu and deployment workflows are configured for dev and prod
- **THEN** each environment uses its own GCP project ID, state backend scope, Artifact Registry repository, GKE cluster, Cloud SQL instance, object storage bucket, Secret Manager secrets, workload service accounts, and CI service accounts

#### Scenario: Production requires approval
- **WHEN** a workflow applies production infrastructure or deploys a production release
- **THEN** it requires the configured production GitHub Environment approval before making production changes

### Requirement: Immutable image build and dev deployment
Backend and frontend image builds SHALL produce immutable images tagged with the full 40-character Git commit SHA, and successful `main` builds SHALL deploy the affected service image to dev using the same SHA.

#### Scenario: Backend image is built and deployed to dev
- **WHEN** backend validation passes on `main`
- **THEN** the backend workflow builds `backend:<40-character git commit sha>`, pushes it to the dev Artifact Registry without any mutable tag, and starts a dev deployment using that exact backend image tag

#### Scenario: Frontend image is built and deployed to dev
- **WHEN** frontend validation passes on `main`
- **THEN** the frontend workflow builds `frontend:<40-character git commit sha>`, pushes it to the dev Artifact Registry without any mutable tag, and starts a dev deployment using that exact frontend image tag

#### Scenario: Unchanged service keeps its current SHA on auto-dev deploys
- **WHEN** only one service's CI workflow runs because a path filter restricted the change
- **THEN** the deploy workflow resolves the other service's image tag from the currently deployed Kubernetes Deployment in the target environment instead of building or selecting a mutable tag

### Requirement: Immutable image tag guard rails
Deploy, release, and CI build workflows SHALL refuse to push, accept, or render mutable image tags. Every tag that reaches a registry or a Kubernetes manifest SHALL be a 40-character lower-case hex Git commit SHA.

#### Scenario: CI workflows do not push mutable tags
- **WHEN** backend or frontend CI builds run
- **THEN** they push a single image tag equal to `${{ github.sha }}` and never push `latest`, branch names, or any other mutable reference

#### Scenario: Deploy workflow rejects mutable or invalid tags
- **WHEN** the deploy workflow receives a manual dispatch with `latest`, an empty tag, a branch name, or any string that is not a 40-character lower-case hex SHA
- **THEN** the workflow aborts before rendering manifests with a clear `::error::` annotation

#### Scenario: Release workflow rejects mutable or invalid tags
- **WHEN** the production release workflow receives an empty tag, `latest`, a branch name, or any string that is not a 40-character lower-case hex SHA
- **THEN** the workflow aborts before promoting images or deploying manifests

#### Scenario: Auto-dev deploys resolve the unchanged service's SHA
- **WHEN** an auto-dev deploy receives only one image tag because a path filter restricted the change
- **THEN** the deploy workflow reads the currently running Deployment's image tag in the target environment and reuses it for the unchanged service instead of defaulting to `latest`

### Requirement: Production release promotion
The system SHALL provide a manual production release workflow that promotes existing backend and frontend 40-character Git commit SHA-tagged images and deploys those promoted images without rebuilding from source.

#### Scenario: Release requires explicit image tags
- **WHEN** an operator starts the production release workflow
- **THEN** the workflow requires both a backend image tag and a frontend image tag as 40-character Git commit SHAs

#### Scenario: Release promotes images into prod registry
- **WHEN** the requested backend and frontend image tags exist in the source registry
- **THEN** the release workflow copies or retags those exact images into the production Artifact Registry before deploying production manifests

#### Scenario: Release does not rebuild images
- **WHEN** the production release workflow runs
- **THEN** it deploys promoted image artifacts and does not run application source builds for backend or frontend

#### Scenario: Release summary records outcome
- **WHEN** the production release workflow completes or fails after deployment begins
- **THEN** the workflow summary records backend tag, frontend tag, source registry, prod registry, GKE cluster, migration result, rollout result, smoke-check result, and release operator context available from GitHub Actions

### Requirement: Cross-project Artifact Registry reader
The system SHALL explicitly grant the destination-environment CI service account cross-project read access to the source-environment Artifact Registry so the production promotion identity can read source images and write destination images.

#### Scenario: Dev project grants prod CI service account reader access
- **WHEN** the dev OpenTofu root is configured with the prod CI service account email through the `prod_promotion_service_account_email` variable
- **THEN** the dev project adds a `google_project_iam_member` binding that grants the prod CI service account `roles/artifactregistry.reader` on the dev project

#### Scenario: Release uses environment-specific identities
- **WHEN** `release.yml` verifies and promotes images
- **THEN** source verification authenticates as the dev CI service account, while promotion authenticates as the prod CI service account that has reader access to the dev registry and writer access to the prod registry

#### Scenario: Operators without a cross-project reader can still promote
- **WHEN** the dev OpenTofu root is configured with an empty `prod_promotion_service_account_email`
- **THEN** no cross-project binding is created and the release workflow must authenticate as a service account that already has read access to the dev registry (for example, by splitting source and destination authentication in the release workflow)

### Requirement: OpenTofu deployment output contract
OpenTofu SHALL expose stable environment outputs consumed by deployment and release workflows instead of requiring hardcoded cloud resource values in Kubernetes manifests or GitHub workflow scripts.

#### Scenario: Deploy workflow reads environment outputs
- **WHEN** the deploy or release workflow targets an environment
- **THEN** it reads OpenTofu outputs for Artifact Registry URL, GKE cluster name and location, runtime service account emails, object storage bucket, Cloud SQL instance connection name, Cloud SQL database name, frontend static IP details, Secret Manager secret references, and Kubernetes namespace

#### Scenario: Release-specific values remain workflow inputs
- **WHEN** Kubernetes manifests are rendered for deployment
- **THEN** image tags, public hostnames, provider defaults, and other release-specific values are supplied by workflow inputs or environment configuration while cloud resource identifiers come from OpenTofu outputs

#### Scenario: Foundation values come from bootstrap outputs
- **WHEN** bootstrap is applied
- **THEN** it publishes remote state bucket names, Workload Identity provider IDs, CI/deploy/IaC service account emails, project IDs, project numbers, and bootstrap recovery values to GitHub repository variables rather than requiring manual copying from dev/prod environment outputs

#### Scenario: Environment outputs are synchronized after apply
- **WHEN** a dev or prod IaC apply succeeds
- **THEN** the post-apply workflow synchronizes an allow-listed set of non-sensitive environment outputs to the matching GitHub repository variables

### Requirement: Deployment verification gates
Deployment and release workflows SHALL verify runtime readiness before reporting success.

#### Scenario: Migration is completed before backend rollout succeeds
- **WHEN** a deploy or release applies manifests containing a migration Job
- **THEN** the workflow waits for the migration Job to complete before considering the backend rollout successful

#### Scenario: Backend and frontend rollouts are verified
- **WHEN** deployment manifests have been applied
- **THEN** the workflow waits for backend and frontend Deployment rollout status to succeed

#### Scenario: Runtime smoke checks pass
- **WHEN** rollouts complete
- **THEN** the workflow verifies backend `/health` and a frontend public HTTP 200 response through the configured Ingress before marking the deploy or release successful

### Requirement: Image-based rollback documentation
The system SHALL document rollback using previous backend and frontend 40-character Git commit SHA image tags, while identifying database migration rollback as a manual restore or forward-fix process.

#### Scenario: Operator rolls back image tags
- **WHEN** a production release must be reverted without a database restore
- **THEN** the documentation explains how to redeploy previous backend and frontend 40-character Git commit SHA image tags or use Kubernetes rollout history when compatible with the database state

#### Scenario: Migration incompatibility is documented
- **WHEN** a migration creates a state incompatible with the desired rollback image
- **THEN** the documentation directs operators to restore from an approved database backup or apply a reviewed forward-fix migration before deploying compatible images
