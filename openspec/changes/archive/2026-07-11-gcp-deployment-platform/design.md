## Context

Fotosintesis is a monorepo with a FastAPI backend, Next.js frontend, Dockerfiles for both services, OpenTofu infrastructure under `infra/opentofu`, and plain Kubernetes manifests under `deploy/k8s`. Existing deployment documentation describes manual OpenTofu planning/apply, manual image builds, manual manifest rendering, and manual Kubernetes rollout checks.

The current infrastructure scaffold already covers core GCP resources: Artifact Registry, GKE with Workload Identity, Cloud SQL for PostgreSQL, Cloud Storage buckets, Secret Manager secret containers, runtime IAM, and monitoring basics. The missing layer is an automated delivery platform that connects repository changes to the correct validation, image build, infrastructure, deployment, and release operations.

This change is operational and infrastructure focused. It does not alter botanical classification, answerability, retrieval, evidence validation, or language-handling semantics. Any deterministic logic introduced by this change is limited to deployment safety, schema/config validation, environment selection, provider selection, URL/health checks, and workflow control.

## Goals / Non-Goals

**Goals:**

- Make GCP deployment reproducible through OpenTofu and GitHub Actions.
- Make remote-state, GitHub OIDC, CI/deploy identities, and foundation IAM reproducible through a local-only OpenTofu bootstrap root.
- Keep dev and prod isolated in separate GCP projects and state scopes.
- Use GitHub OIDC and GCP Workload Identity Federation rather than long-lived CI credentials.
- Build backend and frontend images with immutable Git SHA tags.
- Automatically deploy successful backend/frontend changes to dev from `main`.
- Promote already-built images to prod through a manual `release.yml` workflow with approval.
- Connect GKE workloads to Cloud SQL through Cloud SQL Auth Proxy sidecars.
- Source Kubernetes runtime secrets from Secret Manager through External Secrets Operator.
- Use GCS as durable backend object storage in GCP while preserving local storage for local development.
- Expose frontend through GKE HTTPS Ingress using a reserved static IP and GKE-managed certificate.
- Verify deployment through migration completion, rollout status, backend `/health`, and frontend public response.
- Document bootstrap, secret population, DNS, release, rollback, and cleanup operations.

**Non-Goals:**

- Do not automate database downgrade or schema rollback.
- Do not run bootstrap from GitHub Actions; bootstrap remains a local operator action because it owns the trust path GitHub Actions depends on.
- Do not store Secret Manager secret values in OpenTofu state.
- Do not sync production secret values from GitHub secrets.
- Do not rebuild application images during production release.
- Do not add semantic versioning or GitHub Release publishing in this round.
- Do not fully automate Cloud DNS unless a managed DNS zone is introduced later.
- Do not implement full GCP billing budget automation in this round.
- Do not introduce hardcoded keyword matching, token presence checks, language-specific word lists, or deterministic botanical semantic behavior.

## Decisions

### Use one cohesive change

This work spans infrastructure, backend storage, Kubernetes manifests, GitHub workflows, deployment documentation, and release semantics. Keeping it as one OpenSpec change avoids splitting dependent contracts across separate proposals where CI identity, OpenTofu outputs, manifests, and workflows could drift.

Alternative considered: split by domain. That would improve review granularity but would make the initial platform harder to validate end-to-end.

### Use separate GCP projects for dev and prod

Dev and prod SHALL use separate GCP projects, separate OpenTofu state, separate Artifact Registry repositories, separate service accounts, and separate runtime resources. This limits IAM blast radius and makes promotion to production explicit.

Alternative considered: one shared project with naming conventions. This is cheaper and simpler but weakens isolation and makes production IAM harder to reason about.

### Manage foundation resources through a local-only bootstrap root

OpenTofu SHALL add one local-only `infra/opentofu/bootstrap` root that manages the deployment foundation for both dev and prod projects. The bootstrap root owns the bootstrap state bucket, the dev/prod environment state buckets, required project API enablement, per-project GitHub Workload Identity Federation, CI/deploy service accounts, CI/deploy project IAM, state-bucket IAM, and foundation outputs consumed by GitHub repository variables.

The first bootstrap apply runs with local administrator credentials and local state. After it creates the bootstrap state bucket, the operator migrates bootstrap state to that bucket with the documented backend configuration. The bootstrap root remains local-operator-only after migration; GitHub Actions does not manage the bootstrap root because it owns the OIDC trust path GitHub Actions depends on.

Bootstrap output values SHALL be the source of truth for foundation GitHub variables such as state bucket names, WIF provider IDs, CI service account emails, deploy service account emails, and project identifiers. Dev/prod environment roots SHALL stop outputting bootstrap-owned values and SHALL keep only application/runtime deployment outputs.

Alternative considered: keep remote state buckets and CI/OIDC setup as manual prerequisites. This is faster initially but leaves the most failure-prone part of the platform outside the repository contract.

Alternative considered: manage bootstrap through GitHub Actions after first apply. This improves auditability but lets CI mutate its own trust path and increases recovery risk when OIDC or state access breaks.

### Keep environment roots runtime-focused

The dev/prod OpenTofu environment roots SHALL own runtime infrastructure only: Artifact Registry, GKE, Cloud SQL, application object-storage bucket, Secret Manager containers, static IP, monitoring, backend/frontend runtime service accounts, Kubernetes Workload Identity bindings, runtime IAM roles, and deployment outputs consumed by `deploy.yml`.

Bootstrap-owned concerns SHALL be removed from the environment roots: project service enablement, GitHub OIDC providers, CI/deploy service account creation, CI/deploy project IAM, GitHub principalSet impersonation bindings, remote state bucket creation/IAM, and bootstrap-owned outputs. The implementation SHALL include cleanup verification so these resources do not remain duplicated across OpenTofu states.

Alternative considered: keep the current mixed env roots and add only state buckets to bootstrap. This would preserve the bootstrap paradox where CI needs OIDC and state access before it can safely apply the root that creates OIDC and state access.

### Use path-scoped GitHub workflows

The repository SHALL add separate workflows for backend CI, frontend CI, OpenTofu, deployment, and production release. Path filters keep unrelated changes from running expensive or risky jobs.

Backend and frontend workflows own validation, image build, image push, and dev deploy triggers. The IaC workflow owns OpenTofu format, validation, plan, and apply behavior. The deploy workflow owns Kubernetes application rollout. The release workflow owns production image promotion and production rollout.

Alternative considered: one large pipeline. A single pipeline would be simpler to discover but would run too much work for most changes and blur ownership between source validation, infrastructure, and release promotion.

### Use Git SHA image tags and promotion, not rebuilds

Application images SHALL be tagged with the Git SHA. Production release SHALL promote selected existing image tags into the prod Artifact Registry and deploy those exact tags. It SHALL NOT rebuild from source.

This ensures the production artifact is the same artifact that passed dev validation. The release workflow records the selected backend and frontend tags in the workflow summary.

Alternative considered: semantic version tags only. That improves human-readable releases but adds versioning policy and tagging mechanics that are not required for this round.

### Auto-deploy dev and manually release prod

Successful backend or frontend builds on `main` SHALL auto-deploy to dev. Production deployment SHALL happen only through manual `release.yml` dispatch with prod environment approval and explicit backend/frontend image tags.

Alternative considered: automatic prod deployment from `main`. This was rejected because production Cloud SQL migrations, public ingress, and user-facing releases need an approval boundary.

### Use Cloud SQL Auth Proxy sidecars

Backend Deployment and migration Job pods SHALL use Cloud SQL Auth Proxy sidecars. The application connects to the database through localhost while Workload Identity gives the proxy permission to connect to the Cloud SQL instance.

Alternative considered: private IP/VPC. That is a strong long-term network posture but adds more networking scope than necessary for this deployment round.

### Use Secret Manager with External Secrets Operator

OpenTofu SHALL create Secret Manager secret containers. Operators SHALL add secret versions manually out of band. External Secrets Operator SHALL run in the cluster and materialize the runtime Kubernetes Secret from Secret Manager.

The deploy workflow installs or upgrades a pinned External Secrets Operator release before applying app manifests. This keeps secret values out of Git, out of OpenTofu state, and out of GitHub Actions secrets.

Alternative considered: CI creates Kubernetes Secrets from GitHub secrets. This is easier but duplicates secret authority and exposes runtime secrets to CI logs/processes.

### Add GCS object storage behind the existing backend abstraction

The backend SHALL support `local` and `gcs` object storage providers selected by runtime configuration. Local remains the default for development. GCP environments use GCS with Workload Identity and do not require static storage access keys.

Alternative considered: mount the bucket into the pod. That avoids app code but introduces operational coupling and less explicit failure behavior.

### Use GKE Ingress with managed certificate

OpenTofu SHALL reserve a static IP. Kubernetes manifests SHALL define the frontend Ingress and GKE ManagedCertificate. DNS record creation remains a documented manual step for this round.

Alternative considered: `LoadBalancer` Service. This is simpler but weaker for a production HTTPS/domain story.

### Use image rollback only

Rollback SHALL support redeploying prior backend/frontend image tags or using Kubernetes rollout undo when appropriate. Database migrations are forward-only for this round. Incompatible migration failures require database restore from backup or a reviewed forward-fix migration.

Alternative considered: automated downgrade migrations. This adds significant database lifecycle scope and cannot safely be assumed for every Alembic change.

## Risks / Trade-offs

- [Bootstrap chicken-and-egg] GitHub OIDC cannot manage itself before it exists → A local admin bootstrap apply creates the first trust path, then CI takes over.
- [Duplicate OpenTofu ownership] Moving foundation resources without cleanup can make two states manage the same APIs, service accounts, or IAM bindings → Bootstrap-owned resources must be removed from env roots and verified with lightweight cleanup checks before live validation.
- [Bootstrap state recovery] Bootstrap owns the trust path and state buckets → Bootstrap state must migrate to a dedicated GCS bucket, and configurable `bootstrap_admin_members` must retain recovery access to bootstrap/dev/prod state buckets.
- [Secret version drift] OpenTofu manages secret containers but not values → Documentation must list required secrets and validation/smoke checks must fail clearly when values are missing.
- [External Secrets dependency] App deploy depends on ESO readiness → Deploy workflow installs/upgrades a pinned ESO version and waits for operator availability before applying ExternalSecret resources.
- [Cloud SQL proxy startup race] App containers may start before the proxy is accepting connections → Backend and migration configuration should rely on Kubernetes restart behavior and migration Job retries; readiness checks gate rollout.
- [Forward-only migrations] Image rollback cannot undo incompatible database schema changes → Production releases must run migrations before backend rollout and document restore/forward-fix procedures.
- [DNS remains manual] Frontend HTTPS cannot become healthy until DNS points to the reserved IP → Deployment docs must make DNS a prerequisite for `hostname-https` production smoke checks. `ip-http` mode bypasses DNS and verifies direct HTTP access through the reserved static IP.
- [Cross-project image promotion] Prod release must authenticate to both source/dev and prod registries → Release workflow service account IAM must explicitly allow reading source images and writing prod images. The dev OpenTofu root grants the prod CI service account `roles/artifactregistry.reader` on the dev project through the `iam` module's `cross_project_artifactregistry_readers` input, so a single OIDC-authenticated token covers both the dev source registry login and the prod destination registry write.
- [Cost exposure] GKE and Cloud SQL can incur ongoing cost → Keep baseline monitoring, document resource sizing, and include basic alerting without blocking this round on billing budget automation.

## Migration Plan

1. Confirm no real dev/prod OpenTofu state exists yet, or stop and create an explicit state migration/import plan before moving ownership.
2. Apply `infra/opentofu/bootstrap` locally once with administrator credentials and local state to create the bootstrap state bucket, dev/prod state buckets, required APIs, GitHub OIDC, CI/deploy service accounts, CI/deploy IAM, and state-bucket IAM.
3. Migrate bootstrap state to the bootstrap GCS backend and validate the bootstrap root from the migrated backend.
4. Configure GitHub repository variables/environments from bootstrap outputs and operator-controlled values.
5. Apply dev/prod environment roots through the documented local or CI flow so runtime infrastructure and deployment outputs exist in their environment state buckets.
6. Add required Secret Manager versions manually with `gcloud secrets versions add` for dev and prod.
7. Point DNS records to the reserved frontend static IPs where HTTPS ingress is enabled.
8. Merge backend/frontend/IaC workflow changes and validate dev auto-deployment from `main`.
9. Run a manual prod infrastructure plan/apply with approval.
10. Run `release.yml` with explicit backend and frontend SHA tags that have passed dev.
11. Verify workflow summary, rollout status, backend health, frontend public response, and application logs.

Rollback uses previous image tags. If a database migration creates an incompatible state, restore from backup or apply a reviewed forward-fix migration before redeploying compatible images.

## Open Questions

- Final dev and prod GCP project IDs.
- Final remote state bucket names.
- Bootstrap state bucket name and bootstrap admin member list.
- GitHub repository owner/name values for OIDC attribute conditions.
- Production domain name and whether dev also gets a public HTTPS hostname.
- Notification channel value for baseline monitoring.
- Final provider defaults and required Secret Manager secret names for each environment.
