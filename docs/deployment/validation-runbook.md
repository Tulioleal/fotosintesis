# Validation Runbook

This runbook is the operator procedure for collecting the live
deployment evidence required by the `gcp-deployment-platform` OpenSpec
change. It complements the automated checks in tasks 7.1-7.6, which
run in CI without contacting GCP, and tasks 7.7, 7.8, 10.5-10.13,
which require real GCP projects, real GitHub runs, and a real DNS
zone (for `hostname-https`).

The full evidence template is in `validation-evidence.md`.

## Sandbox dry-run evidence (collected by CI)

The CI workflows run the following checks automatically and post the
results under "Sandbox dry-run" in `validation-evidence.md`:

- `tofu fmt -recursive -check` in the IaC workflow.
- `tofu validate` for `infra/opentofu/envs/{dev,prod}`.
- Offline `tofu plan -input=false -refresh=false` for dev and prod.
  The plan is shape-only: it does not authenticate to GCP, read remote
  state, refresh live cloud objects, or validate drift. Treat it as
  informational.
- `backend-ci.yml` and `frontend-ci.yml` lint + test jobs.
- Actionlint against every workflow file.

Sandbox checks are a precondition for live validation. Do not skip them.

## Dev environment prerequisites

The dev operator must confirm the following before running the dev
end-to-end evidence:

1. **Dev GCP project** exists. The project number is in
   `terraform.tfvars` for the bootstrap root.
2. **Project APIs** are enabled through the bootstrap root:
   `container.googleapis.com`, `artifactregistry.googleapis.com`,
   `sqladmin.googleapis.com`, `secretmanager.googleapis.com`,
   `iam.googleapis.com`, `iamcredentials.googleapis.com`,
   `storage.googleapis.com`, `monitoring.googleapis.com`,
   `compute.googleapis.com`, `cloudresourcemanager.googleapis.com`.
3. **Dev state bucket** is created by bootstrap and the dev OpenTofu
   root has been initialized under the `fotosintesis/dev` prefix.
4. **GitHub foundation variables** are published by the bootstrap
   root: `DEV_TF_STATE_BUCKET`, `DEV_GCP_PROJECT_ID`,
   `DEV_GCP_PROJECT_NUMBER`, `DEV_CI_SERVICE_ACCOUNT_EMAIL`,
   `DEV_DEPLOY_SERVICE_ACCOUNT_EMAIL`, `DEV_IAC_SERVICE_ACCOUNT_EMAIL`,
   `DEV_WIF_PROVIDER_ID`, `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL`.
   **Per-environment output variables** (`DEV_ARTIFACT_REGISTRY_URL`,
   `DEV_OBJECT_STORAGE_BUCKET`, `DEV_STATIC_IP_NAME`, etc.) are
   published by the iac.yml post-apply sync job after a successful
   dev apply.
5. **Secret Manager entries** exist with at least one version for
   `fotosintesis-database-url`, `fotosintesis-auth-secret`,
   `fotosintesis-openai-api-key`, and `fotosintesis-gemini-api-key`.
   Dev/mock environments may use documented placeholders for provider
   families that are fully mocked. The population commands are in
   `external-secrets.md`.
6. **`FRONTEND_EXPOSURE_MODE`** is set. For `hostname-https`, dev DNS
   points to the reserved static IP name
   (`fotosintesis-dev-frontend-ip`) so the frontend HTTPS smoke check
   can reach the ManagedCertificate-backed ingress. For `ip-http`,
   direct HTTP access through the reserved static IP is acceptable.

## Dev end-to-end evidence

1. Trigger `iac.yml` on `main` (or dispatch manually with
   `environment: dev`, `tofu_command: apply`) to ensure the dev env
   root is up to date. The apply authenticates as
   `DEV_IAC_SERVICE_ACCOUNT_EMAIL`. The post-apply sync job then
   publishes the dev outputs to repository variables. Record the run
   URL.
2. Push a backend (or frontend) change to `main` so `backend-ci.yml`
   (or `frontend-ci.yml`) builds the image and triggers `deploy.yml`.
   `backend-ci.yml` and `frontend-ci.yml` authenticate as
   `DEV_CI_SERVICE_ACCOUNT_EMAIL` (the image-CI account, not the IaC
   account). Record the run URLs.
3. Confirm the deploy summary records:
   - Backend image tag and frontend image tag (40-character Git commit
     SHAs).
   - Migration `pass`.
   - Rollout `pass`.
   - Required provider API keys `pass`.
   - Backend in-cluster smoke `pass`.
   - Frontend public smoke `pass` (or document the DNS gap when
     `ip-http` is in use).
4. Save the workflow run URLs and the per-step `pass`/`fail` results
   in `validation-evidence.md` under "Dev end-to-end."

The dev evidence satisfies task 7.7 only when every gate reports
`pass` and the run URLs are recorded.

## Prod environment prerequisites

The prod operator must confirm:

1. **Prod GCP project** exists with the project number configured in
   the bootstrap root.
2. **Project APIs** are enabled through the bootstrap root.
3. **Prod state bucket** is created by bootstrap and the prod OpenTofu
   root has been initialized under the `fotosintesis/prod` prefix.
4. **GitHub prod environment** has at least one configured reviewer.
5. **Secret Manager entries** exist with production versions.
6. **DNS** points the production hostname to the prod static IP.

## Prod release evidence

1. Trigger `iac.yml` against `prod` with `tofu_command: apply` and the
   configured reviewer approval. The apply authenticates as
   `PROD_IAC_SERVICE_ACCOUNT_EMAIL`; the post-apply sync job then
   publishes the prod outputs to repository variables. Record the run
   URL.
2. Trigger `release.yml` with the two 40-character SHAs that passed
   dev. `verify-source-images` authenticates as
   `DEV_CI_SERVICE_ACCOUNT_EMAIL` and confirms the tags exist in the
   dev registry. `promote-images` authenticates as
   `PROD_CI_SERVICE_ACCOUNT_EMAIL` and copies them to the prod
   registry. `deploy-prod` authenticates as
   `PROD_DEPLOY_SERVICE_ACCOUNT_EMAIL` and runs the prod apply. The
   `summary` job aggregates the per-gate results.
3. Confirm the summary records:
   - Verify source images: `success`.
   - Promote images: `success`.
   - Deploy: `success` with `migration=pass`, `rollout=pass`,
     `required_keys=pass`, `backend_smoke=pass`, `frontend_smoke=pass`.
4. Save the run URLs and per-gate results in `validation-evidence.md`
   under "Prod release."

The prod evidence satisfies task 7.8 only when every gate reports
`pass` and the live run URLs are recorded.

## Sandbox-only run URLs

The `Sandbox dry-run` section in `validation-evidence.md` records CI
runs that do not authenticate to GCP. The expected contents are:

- `tofu fmt -recursive -check` run URL.
- `tofu validate` for dev and prod run URLs.
- `tofu plan -input=false -refresh=false` for dev and prod (shape-only,
  partial).
- `backend-ci.yml` and `frontend-ci.yml` lint/test run URLs.
- `actionlint` run URL.

## When sandbox checks are sufficient

The `gcp-deployment-platform` change is eligible for archive only when
both the dev end-to-end and prod release evidence have per-step
`pass` results and live run URLs. Sandbox dry-run evidence is
informational; it does not satisfy 7.7 or 7.8. The operator must run
the live steps and record the URLs.
