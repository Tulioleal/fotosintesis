# GitHub Repository and Environment Variables

The deploy, OpenTofu, and release workflows read foundation values from
GitHub repository variables. Per-environment values are stored as GitHub
Environment variables. The two-tier design lets the bootstrap root own
foundation IAM/state/WIF without leaking it into environment-level
configuration.

## Foundation (repository variables)

Set these on the **repository** (Settings -> Secrets and variables ->
Actions -> Variables -> Repository tab). Values come from the bootstrap
root's `tofu output -json`.

| Variable | Source |
| --- | --- |
| `TF_STATE_BUCKET` | Bootstrap `dev_state_bucket` output when targeting dev, `prod_state_bucket` when targeting prod. Set per environment below instead. |
| `WIF_PROVIDER_ID` | Bootstrap `dev_wif_provider_id` for dev, `prod_wif_provider_id` for prod. |
| `DEPLOY_SERVICE_ACCOUNT_EMAIL` | Bootstrap `dev_deploy_service_account_email` for dev, `prod_deploy_service_account_email` for prod. |
| `DEV_GCP_PROJECT_ID` | Bootstrap `dev_project_id`. |
| `PROD_GCP_PROJECT_ID` | Bootstrap `prod_project_id`. |
| `DEV_CI_SERVICE_ACCOUNT_EMAIL` | Bootstrap `dev_ci_service_account_email`. |
| `PROD_CI_SERVICE_ACCOUNT_EMAIL` | Bootstrap `prod_ci_service_account_email`. |
| `DEV_ARTIFACT_REGISTRY_URL` | Dev env root `artifact_repository_url` output, e.g. `us-central1-docker.pkg.dev/<dev-project>/fotosintesis`. |
| `PROD_ARTIFACT_REGISTRY_URL` | Prod env root `artifact_repository_url` output. |
| `DEV_OBJECT_STORAGE_BUCKET` | Dev env root `object_storage_bucket` output. |
| `PROD_OBJECT_STORAGE_BUCKET` | Prod env root `object_storage_bucket` output. |
| `DEV_STATIC_IP_NAME` | Dev env root `frontend_static_ip_name` output (default `fotosintesis-dev-frontend-ip`). |
| `PROD_STATIC_IP_NAME` | Prod env root `frontend_static_ip_name` output (default `fotosintesis-prod-frontend-ip`). |
| `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL` | The prod CI service account email. The dev OpenTofu root grants it `roles/artifactregistry.reader` so a single OIDC token in `release.yml` can both verify dev source images and copy them into the prod registry. Mapped to `TF_VAR_prod_promotion_service_account_email` in `iac.yml`. |
| `GCP_REGION` | GCP region for the env roots (default `us-central1`). |
| `NOTIFICATION_EMAIL` | Optional. Email address that receives the dev/prod monitoring alerts. |
| `EXTERNAL_SECRETS_OPERATOR_VERSION` | Pinned External Secrets Operator version the deploy workflow installs (default `0.10.4`). |
| `DEFAULT_REPLICAS_DEV` | Backend/frontend replica count for the dev deploy (default `1`). |
| `DEFAULT_REPLICAS_PROD` | Backend/frontend replica count for the prod deploy (default `2`). |
| `FRONTEND_EXPOSURE_MODE` | `hostname-https` (GKE-managed certificate, requires DNS) or `ip-http` (direct HTTP through the reserved static IP). |
| `FRONTEND_HOSTNAME` | Public hostname (only required when `FRONTEND_EXPOSURE_MODE=hostname-https`). |
| `MANAGED_CERTIFICATE_NAME` | Name of the GKE `ManagedCertificate` resource (only required when `FRONTEND_EXPOSURE_MODE=hostname-https`). |
| `CLOUD_SQL_PROXY_IMAGE` | Cloud SQL Auth Proxy image (default `gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.15.2`). |
| `CLOUD_SQL_PROXY_PORT` | Cloud SQL Auth Proxy port (default `5432`). |
| `DATABASE_URL_SECRET_KEY` | Key inside the runtime Secret that holds `database-url` (default `database-url`). |
| `AUTH_SECRET_SECRET_KEY` | Key inside the runtime Secret that holds the auth secret (default `auth-secret`). |
| `MODEL_PROVIDER`, `VISION_PROVIDER`, `JUDGE_PROVIDER`, `SEARCH_PROVIDER`, `EMBEDDING_PROVIDER` | Per-role default provider. `mock` is the safe default. |
| `MODEL_PROVIDERS`, `VISION_PROVIDERS`, `JUDGE_PROVIDERS`, `SEARCH_PROVIDERS` | Comma-separated fallback chain for each role. When set, the deploy workflow verifies each provider's API key is projected by the runtime Secret. |
| `OPENAI_TEXT_MODEL` ... `GEMINI_SEARCH_MODEL` | Provider-specific model names. |
| `EMBEDDING_DIMENSION` | Vector dimension for the embeddings table. |
| `FRONTEND_API_BASE_URL` | Public URL the browser uses to reach the backend. |
| `FRONTEND_SERVER_API_BASE_URL` | Internal URL the Next.js server uses to reach the backend (default `http://fotosintesis-backend:8000`). |

## Per-environment overrides

The `iac.yml` workflow uses `TF_VAR_*` exports to pass per-environment
values into OpenTofu without leaking them into the dev/prod
`variables.tf` defaults:

- `iac.yml` (PR plan): reads `DEV_*` / `PROD_*` repository variables and
  sets `TF_VAR_project_id`, `TF_VAR_object_storage_bucket`,
  `TF_VAR_frontend_static_ip_name`, and
  `TF_VAR_prod_promotion_service_account_email` (dev only).
- `iac.yml` (manual): same as PR plan.
- `iac.yml` (auto-apply on main, dev): uses `vars.DEV_*` repository
  variables to plan/apply the dev env root.
- `deploy.yml`: uses `vars.TF_STATE_BUCKET`, `vars.WIF_PROVIDER_ID`,
  `vars.DEPLOY_SERVICE_ACCOUNT_EMAIL`, and the per-environment
  foundation variables to authenticate and read OpenTofu outputs.
- `release.yml`: uses `vars.DEV_*` to verify source images and
  `vars.PROD_*` to copy them into the prod registry.

## Secrets

The workflow set does not require any GitHub Actions secrets. All
authentication uses GitHub OIDC and GCP Workload Identity Federation. Do
not commit GCP service account JSON keys to the repository or store them
in GitHub secrets.

The frontend build needs a placeholder `AUTH_SECRET` to satisfy
NextAuth's build-time check. Configure a repository variable
`FRONTEND_BUILD_AUTH_SECRET` (or use the default placeholder) for that
purpose only. The runtime `AUTH_SECRET` is projected from Secret Manager
through External Secrets.

## Sanity check

After configuring the variables, run a manual `iac.yml` dispatch with
`environment=dev` and `tofu_command=plan`. The plan should reflect the
configured variables and report `No changes` when the bootstrap root
was already applied.
