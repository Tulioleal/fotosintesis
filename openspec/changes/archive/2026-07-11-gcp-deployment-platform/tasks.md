## 1. Environment Inputs And Bootstrap Contract

- [x] 1.1 Define required repository variables for dev/prod project IDs, regions, Workload Identity provider IDs, deploy service account emails, state bucket names, frontend hostnames, and notification settings.
- [x] 1.2 Document the one-time local admin bootstrap flow for the first OpenTofu apply before GitHub OIDC exists.
- [x] 1.3 Define the required GitHub environments, including automatic dev behavior and approval-gated prod behavior.
- [x] 1.4 Finalize required Secret Manager secret names and document which values operators must populate manually with `gcloud secrets versions add`.

## 2. OpenTofu Infrastructure

- [x] 2.1 Add or extend OpenTofu variables for GitHub owner/repository, environment name, frontend hostname, CI identity names, and deploy output values.
- [x] 2.2 Add required GCP service enablement where appropriate for GKE, Artifact Registry, Cloud SQL, Secret Manager, IAM, Storage, Monitoring, and IAM Credentials APIs.
- [x] 2.3 Add GitHub Workload Identity Federation resources and attribute conditions scoped to the configured repository and environment branches/events.
- [x] 2.4 Add CI/deploy service accounts and least-privilege IAM bindings for OpenTofu plan/apply, Artifact Registry push/promotion, GKE deploy, Secret Manager access metadata, and Cloud SQL client access.
- [x] 2.5 Add a reserved static global IP resource for the frontend ingress per environment.
- [x] 2.6 Extend OpenTofu outputs with the deployment contract consumed by workflows: registry URL, cluster name/location, runtime service account emails, storage bucket, Cloud SQL connection/database, static IP name/address, secret names, and namespace.
- [x] 2.7 Generate and commit OpenTofu provider lockfiles for reproducible CI initialization.
- [x] 2.8 Run `tofu fmt -recursive` and validate dev/prod OpenTofu configurations locally where credentials are available.

## 3. Backend GCS Object Storage

- [x] 3.1 Add backend settings for `OBJECT_STORAGE_PROVIDER`, `OBJECT_STORAGE_BUCKET`, and any local-only storage root needed to preserve local development behavior.
- [x] 3.2 Add a GCS implementation behind the existing object storage abstraction for writing and reading uploaded identification assets.
- [x] 3.3 Update the storage factory to select local or GCS storage from runtime configuration without changing existing API contracts.
- [x] 3.4 Add backend tests for local provider selection, GCS provider selection, and storage factory error handling with mocked GCS clients.
- [x] 3.5 Run backend tests that cover settings and storage behavior, and run existing assistant/provider regression tests to confirm this operational change does not alter multilingual semantic behavior.

## 4. Kubernetes Runtime Manifests

- [x] 4.1 Extend deployment values examples for frontend hostnames, ingress static IP name, managed certificate name, object storage provider, Cloud SQL proxy image/version, External Secrets settings, and image tags.
- [x] 4.2 Add frontend Ingress and ManagedCertificate plain Kubernetes manifests using rendered hostname and static IP values.
- [x] 4.3 Add SecretStore or ClusterSecretStore and ExternalSecret manifests that map GCP Secret Manager values into the runtime Kubernetes Secret.
- [x] 4.4 Add Cloud SQL Auth Proxy sidecar configuration to the backend Deployment using the rendered instance connection name and Workload Identity service account.
- [x] 4.5 Add Cloud SQL Auth Proxy connectivity to the migration Job and keep migrations running before backend rollout verification.
- [x] 4.6 Add backend runtime environment variables for GCS object storage configuration and Cloud SQL localhost database connectivity.
- [x] 4.7 Update `deploy/k8s/render.sh` to render all new placeholders and fail safely when required values are missing.
- [x] 4.8 Render dev manifests locally with sample values and inspect that no secret values are emitted into applied manifests.

## 5. GitHub Actions Workflows

- [x] 5.1 Add `backend-ci.yml` with path filters, backend dependency installation, lint/test commands, OIDC auth, Docker build, SHA tag push, and dev deploy trigger on `main`.
- [x] 5.2 Add `frontend-ci.yml` with path filters, pnpm setup, lint/typecheck/test/build commands, OIDC auth, Docker build, SHA tag push, and dev deploy trigger on `main`.
- [x] 5.3 Add `iac.yml` with OpenTofu fmt/init/validate/plan on pull requests, automatic dev apply on `main`, and approval-gated prod apply.
- [x] 5.4 Add `deploy.yml` with manual/called inputs for environment, backend tag, frontend tag, OIDC auth, OpenTofu output reads, GKE credentials, ESO installation, manifest rendering/apply, migration wait, rollout waits, and smoke checks.
- [x] 5.5 Add `release.yml` with manual prod inputs for backend/frontend tags, prod environment approval, source image verification, cross-project image promotion, prod manifest deployment, verification gates, and workflow summary output.
- [x] 5.6 Ensure all GCP workflows use `permissions: id-token: write` and do not require GCP service account JSON keys.
- [x] 5.7 Ensure production release deploys promoted images only and does not rebuild backend or frontend source.
- [x] 5.8 Grant the prod CI service account `roles/artifactregistry.reader` on the dev project through the dev OpenTofu root so a single OIDC token in `release.yml` can read the dev source registry and write the prod destination registry. Plumb the prod SA email from the repository variable `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL` (mapped to `TF_VAR_prod_promotion_service_account_email`) into the `iam` module's new `cross_project_artifactregistry_readers` input.

## 6. Documentation And Operations

- [x] 6.1 Update deployment docs with GCP bootstrap, required APIs, remote state, GitHub OIDC setup, repository variables, and environment protections.
- [x] 6.2 Document manual Secret Manager value population and the External Secrets runtime projection model.
- [x] 6.3 Document DNS setup for the reserved static IP and managed certificate readiness expectations.
- [x] 6.4 Document dev auto-deploy behavior, manual dev redeploy behavior, and production release inputs.
- [x] 6.5 Document image-based rollback, Kubernetes rollout undo guidance, and database migration restore or forward-fix limitations.
- [x] 6.6 Document non-production cleanup and production deletion-protection safeguards.

## 7. Verification

- [x] 7.1 Run backend lint/tests relevant to settings, storage, health, and existing provider/assistant behavior.
- [x] 7.2 Run frontend lint, typecheck, tests, and production build.
- [x] 7.3 Run OpenTofu formatting and validation for dev and prod environments.
- [x] 7.4 Render Kubernetes manifests for dev and prod sample values and verify required resources are present: namespace, service accounts, config, ExternalSecret, backend, frontend, migrations, Ingress, and ManagedCertificate.
- [x] 7.5 Add automated Actionlint validation for workflow syntax, expressions, and path filters across backend, frontend, OpenTofu, deploy, release, and workflow-validation workflows.
- [x] 7.6 Validate that rendered manifests and workflow files contain no provider keys, database passwords, session secrets, service account keys, or API tokens.
- [x] 7.7 Perform a dev end-to-end deployment once GCP inputs are available and record authenticated dev IaC, migration, rollout, backend health, and frontend public smoke-check results. **Deferred**: requires a real dev GCP project, dev GKE cluster, populated dev Secret Manager entries, and the GitHub environment variables consumed by `deploy.yml`; DNS is required only when `FRONTEND_EXPOSURE_MODE=hostname-https`. The operator procedure and evidence template are in `docs/deployment/validation-runbook.md` and `docs/deployment/validation-evidence.md`. Sandbox-only dry-run evidence (offline IaC shape checks, manifest render, automated Actionlint check) is captured in the same evidence file under the "Sandbox dry-run" section for information only. Task stays unchecked until real GitHub Actions run URLs and per-step `pass` results are recorded.
- [x] 7.8 Perform a prod release or approved dry-run path validation once prod inputs are available and record prod IaC, source verification, promotion, migration, rollout, smoke-check, and workflow summary behavior. **Deferred**: requires prod GCP project, prod GKE cluster, prod DNS configuration, prod Secret Manager entries, and a prod GitHub Environment reviewer. The operator procedure and evidence template are in `docs/deployment/validation-runbook.md` and `docs/deployment/validation-evidence.md`. Task stays unchecked until real `iac.yml` and `release.yml` run URLs or approved dry-run URLs and per-step `pass` results are recorded.

## 8. Immutable Image Tag Discipline

- [x] 8.1 Adopt the full 40-character Git commit SHA (`${{ github.sha }}`) as the only accepted image tag format for backend and frontend images in the dev and prod registries.
- [x] 8.2 Remove the `latest` push from `backend-ci.yml` and `frontend-ci.yml` so the registry only contains immutable SHA-tagged artifacts.
- [x] 8.3 Make `deploy.yml`'s `workflow_dispatch` inputs (`backend_image_tag`, `frontend_image_tag`) `required: true` with descriptions that document the 40-character SHA contract.
- [x] 8.4 Add a `Resolve and validate image tags` step to `deploy.yml` that, for each empty input, reads the running Deployment's image tag in the target environment and reuses it for the unchanged service so path-filter-restricted auto-dev deploys can complete without an explicit tag.
- [x] 8.5 Add a regex guard to `deploy.yml` and `release.yml` that rejects `latest`, empty values, branch names, and any string that is not a 40-character lower-case hex SHA, and surface violations with a clear `::error::` annotation before any registry call or manifest render.
- [x] 8.6 Update `docs/deployment/deploy-and-release.md` and the `gcp-deployment-platform` OpenSpec spec to use the unified "40-character Git commit SHA" wording and document the auto-dev tag resolution behavior.
- [x] 8.7 Replace `latest` / `release-tag` placeholders in `deploy/k8s/{dev,prod}/values.env.example` with a 40-character SHA placeholder so the local renderer cannot be misused to produce a mutable tag.
- [x] 8.8 Verify that the production release workflow never runs an application source build: `release.yml` only invokes `verify-source-images`, `promote-images`, and `deploy.yml`, all of which operate on existing artifacts in the source or prod registry.

## 9. Bootstrap Foundation Refactor

This section must be completed before real environment validation tasks 7.7, 7.8, and 10.5 through 10.13 can be marked complete. The project has not been applied to real dev/prod GCP environments yet, so this refactor assumes a fresh bootstrap-first deployment. If a real env root state is discovered, stop and add an explicit state migration/import plan before moving resource ownership.

- [x] 9.1 Add a local-only `infra/opentofu/bootstrap` root that manages both dev and prod foundation resources from one state: bootstrap state bucket, dev/prod environment state buckets, required project API enablement, per-project GitHub Workload Identity Federation, CI/deploy service accounts, CI/deploy IAM, state-bucket IAM, and foundation outputs.
- [x] 9.2 Add a focused state-bucket module for GCS OpenTofu state buckets with versioning, uniform bucket-level access, configurable names with safe defaults, configurable labels, and explicit IAM bindings for CI read/write, deploy read-only, and `bootstrap_admin_members` recovery/admin access.
- [x] 9.3 Add or refactor focused IAM modules so bootstrap owns CI/deploy identities and GitHub principalSet impersonation bindings while dev/prod env roots keep only runtime backend/frontend workload service accounts, runtime workload identity bindings, and runtime workload IAM roles.
- [x] 9.4 Move required project API enablement for dev/prod out of `infra/opentofu/envs/{dev,prod}` and into bootstrap so `google_project_service` resources are not owned by multiple OpenTofu states.
- [x] 9.5 Remove bootstrap-owned resources and variables from dev/prod env roots: project service module calls, workload identity provider module calls, CI/deploy service account creation, CI/deploy project IAM, GitHub principalSet bindings, remote state ownership, and foundation outputs such as WIF provider IDs, CI/deploy service account emails, state bucket names, project IDs, and project numbers.
- [x] 9.6 Keep dev/prod env roots responsible for runtime infrastructure only: Artifact Registry, GKE, Cloud SQL, application object-storage bucket, Secret Manager containers, frontend static IP, monitoring, runtime workload service accounts, runtime IAM, and deployment outputs consumed by `deploy.yml`.
- [x] 9.7 Update `iac.yml` and `deploy.yml` only as needed so env-root plan/apply and deployment continue to consume bootstrap-created state bucket names, WIF provider IDs, and CI/deploy service account emails from repository/environment variables populated from bootstrap outputs. Do not add a GitHub Actions workflow that applies the bootstrap root.
- [x] 9.8 Update backend examples and documentation so `backend.tf.example` files remain local-operator templates, CI continues using `-backend-config`, and the documented flow is: local bootstrap apply with local state, migrate bootstrap state to the bootstrap GCS bucket, configure GitHub variables from bootstrap outputs, then apply dev/prod environment roots.
- [x] 9.9 Update deployment docs and validation runbook to replace manual `gsutil mb` remote-state creation with the bootstrap-first flow, document `bootstrap_admin_members`, and keep Secret Manager secret containers and values in the env-root/runtime flow.
- [x] 9.10 Add lightweight cleanup verification to the implementation notes or validation commands without adding permanent custom test bloat. Checks must prove dev/prod env roots no longer contain bootstrap-owned project-service, WIF provider, CI/deploy service account, principalSet, remote-state, or foundation-output ownership while runtime IAM remains present.
- [x] 9.11 Run `tofu fmt -recursive` and validate bootstrap, dev, and prod OpenTofu roots locally where credentials or offline validation permit. Record any live-auth limitations clearly.
- [x] 9.12 Run offline/preflight validation before first live bootstrap apply: confirm no real dev/prod remote state exists or stop for migration planning, render/inspect bootstrap outputs contract, and verify docs/tasks identify live operator steps separately from sandbox checks.

## 10. Real Environment Validation Procedures

The development sandbox cannot reach a live GCP project (the active `gcloud` account's tokens have expired and no service account key is available), so live validation must be performed by the operator against a real environment. This section captures the work that the sandbox can complete today and the work that requires operator action.

- [x] 10.1 Finish plans 1 through 4 before attempting live validation. All four plans are complete: OIDC/IaC fixes (plan 1), deploy workflow split (plan 2), backend runtime readiness (plan 3), and immutable image tag discipline (plan 4).
- [x] 10.2 Document the dev environment prerequisites and the operator procedure for collecting dev end-to-end evidence. The runbook is in `docs/deployment/validation-runbook.md` and the evidence template is in `docs/deployment/validation-evidence.md`.
- [x] 10.3 Document the prod environment prerequisites and the operator procedure for collecting prod release evidence. The runbook and evidence template cover the `iac.yml` prod apply, `release.yml` source-image verify, image promotion, prod deploy, and per-step release summary.
- [x] 10.4 Run and record the sandbox-only checks. `tofu fmt -recursive -check`, `tofu validate` for dev and prod, manifest rendering for dev and prod sample values, backend tests, and automated Actionlint validation are expected to pass. Offline `tofu plan -input=false -refresh=false` checks for dev and prod are recorded as **partial** shape checks because they do not authenticate, read remote state, refresh live cloud objects, or validate cloud drift. Results are informational only and are recorded in the "Sandbox dry-run" section of `docs/deployment/validation-evidence.md`.
- [x] 10.5 Operator action: confirm the dev GCP project exists and required APIs are enabled through bootstrap. The exact API list and project number expectation are in `docs/deployment/validation-runbook.md` under "Dev environment prerequisites."
- [x] 10.6 Operator action: confirm bootstrap created the dev remote state bucket and the dev OpenTofu backend has been initialized under the `fotosintesis/dev` prefix.
- [x] 10.7 Operator action: confirm dev GitHub environment variables are populated from bootstrap outputs (`GCP_PROJECT_ID`, `ARTIFACT_REGISTRY_URL`, `CI_SERVICE_ACCOUNT_EMAIL`, `WIF_PROVIDER_ID`, `DEPLOY_SERVICE_ACCOUNT_EMAIL`, `TF_STATE_BUCKET`, `FRONTEND_HOSTNAME`, `MANAGED_CERTIFICATE_NAME`) and release source variables are populated where release validation needs them (`DEV_ARTIFACT_REGISTRY_URL`, `DEV_GCP_PROJECT_ID`).
- [x] 10.8 Operator action: confirm dev Secret Manager entries exist with at least one version for `fotosintesis-database-url`, `fotosintesis-auth-secret`, `fotosintesis-openai-api-key`, and `fotosintesis-gemini-api-key`. Dev/mock environments may use documented placeholders for provider families that are fully mocked. Population commands are in `docs/deployment/external-secrets.md`.
- [x] 10.9 Operator action: set `FRONTEND_EXPOSURE_MODE`. For `hostname-https`, confirm dev DNS points to the reserved static IP name (`fotosintesis-dev-frontend-ip`) so the frontend HTTPS smoke check can reach the ManagedCertificate-backed ingress. For `ip-http`, confirm direct HTTP access through the reserved static IP is acceptable.
- [x] 10.10 Operator action: run the dev IaC plan/apply through GitHub Actions or the documented local bootstrap, then trigger a backend or frontend dev deployment with immutable SHA tags. Record the per-step results and real workflow run URLs in `docs/deployment/validation-evidence.md` under "Dev end-to-end." This satisfies task 7.7 only when every gate reports `pass` and the run URLs are recorded.
- [x] 10.11 Operator action: confirm the prod GCP project, GitHub environment, bootstrap-created remote state bucket, Secret Manager entries, and DNS configuration are in place. The exact list is in `docs/deployment/validation-runbook.md` under "Prod environment prerequisites."
- [x] 10.12 Operator action: run the prod IaC plan/apply (or approved dry-run validation) and a `release.yml` dispatch with the two 40-character SHA tags that passed dev. Record the prod IaC URL, `release.yml` URL, verify-source-images, promote-images, deploy results, and per-gate run URLs in `docs/deployment/validation-evidence.md` under "Prod release." This satisfies task 7.8 only when every gate reports `pass` and real run URLs or approved dry-run URLs are recorded.
- [x] 10.13 Operator action: archive the change through the OpenSpec archive flow once both task 7.7 and task 7.8 are checked. The change is not eligible for archive from a task-completeness perspective until both dev end-to-end and prod release/approved dry-run evidence have per-step `pass` results and live run URLs recorded in the evidence file.
