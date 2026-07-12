# GitHub Repository and Environment Variables

The deploy, OpenTofu, and release workflows read configuration from
GitHub repository variables. GitHub Environments provide deployment
protection rules, not environment-scoped configuration. This keeps
bootstrap-owned foundation IAM/state/WIF values distinct from
post-apply environment outputs and operator-provided runtime settings.

## Ownership

| Owner | Variables |
| --- | --- |
| Bootstrap (local apply, publishes through the GitHub provider) | Foundation identifiers, state buckets, CI/deploy/IaC service-account emails, WIF provider IDs, project IDs and numbers, prod promotion service account. |
| iac.yml post-apply sync jobs | Per-environment outputs: artifact registry URLs, workload service-account emails, object-storage bucket, Cloud SQL database/connection names, GKE cluster name and location, Kubernetes namespace, runtime secret name, static IP name and address, secret-names JSON. |
| Operator (hand-set) | Provisioning inputs and runtime configuration: GCP region, notification email, frontend exposure mode, hostname, managed certificate, object-storage bucket inputs (first apply), static-IP name inputs (first apply), replica counts, model names and selection, embedding dimension, External Secrets Operator version, Cloud SQL proxy image and port, secret keys, frontend API URLs. |
| GitHub Actions secret | `ACTIONS_VARIABLES_TOKEN` for post-apply repository variable sync, and `FRONTEND_BUILD_AUTH_SECRET` as a NextAuth build-time placeholder only. Runtime secret values live in GCP Secret Manager. |

## Foundation (published by bootstrap)

Bootstrap publishes the following GitHub repository variables to the
target repository through the GitHub provider. A second `tofu apply`
is idempotent: the GitHub provider creates-or-updates each variable
without duplicating it.

| Variable | Source |
| --- | --- |
| `DEV_TF_STATE_BUCKET` | bootstrap `dev_state_bucket` output |
| `PROD_TF_STATE_BUCKET` | bootstrap `prod_state_bucket` output |
| `DEV_GCP_PROJECT_ID` | bootstrap `dev_project_id` input |
| `PROD_GCP_PROJECT_ID` | bootstrap `prod_project_id` input |
| `DEV_GCP_PROJECT_NUMBER` | bootstrap `dev_project_number` input |
| `PROD_GCP_PROJECT_NUMBER` | bootstrap `prod_project_number` input |
| `DEV_CI_SERVICE_ACCOUNT_EMAIL` | bootstrap `dev_ci_service_account_email` output |
| `PROD_CI_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_ci_service_account_email` output |
| `DEV_DEPLOY_SERVICE_ACCOUNT_EMAIL` | bootstrap `dev_deploy_service_account_email` output |
| `PROD_DEPLOY_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_deploy_service_account_email` output |
| `DEV_IAC_SERVICE_ACCOUNT_EMAIL` | bootstrap `dev_iac_service_account_email` output |
| `PROD_IAC_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_iac_service_account_email` output |
| `DEV_WIF_PROVIDER_ID` | bootstrap `dev_wif_provider_id` output |
| `PROD_WIF_PROVIDER_ID` | bootstrap `prod_wif_provider_id` output |
| `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL` | bootstrap `prod_ci_service_account_email` output |

The bootstrap root reads `GITHUB_TOKEN` from the local operator's
environment. The token never lands in `terraform.tfvars`, OpenTofu
outputs, or state. Operators must export a fine-grained personal
access token (PAT) restricted to the target repository and to
"Actions variables: Write" before running the bootstrap apply.

## Environment outputs (published by iac.yml sync jobs)

The iac.yml `sync-dev-outputs` and `sync-manual-outputs` jobs
re-authenticate as the matching IaC identity (`DEV_IAC_SERVICE_ACCOUNT_EMAIL`
or `PROD_IAC_SERVICE_ACCOUNT_EMAIL`), initialize the matching remote
backend, read `tofu output -json`, and publish the allow-listed
non-sensitive outputs to repository variables. Sensitive outputs are
rejected and the output JSON is never echoed to logs. The jobs only
run after a successful apply (auto-apply on main for dev, manual apply
for dev or prod); they never run after plan-only, PR, failed, or
cancelled workflows. The post-apply sync jobs require the repository
secret `ACTIONS_VARIABLES_TOKEN`, which must be a fine-grained PAT
restricted to the target repository with repository Variables write
permission. If the secret is missing, the job fails early with a clear
error. The built-in GitHub Actions token is not used for repository
variable sync. The post-apply sync jobs have `actions: write` permission;
no other iac.yml job has that permission.

| Variable | Source output |
| --- | --- |
| `DEV_ARTIFACT_REGISTRY_URL` / `PROD_ARTIFACT_REGISTRY_URL` | `artifact_repository_url` |
| `DEV_GCP_PROJECT_ID` / `PROD_GCP_PROJECT_ID` | `project_id` |
| `DEV_BACKEND_SERVICE_ACCOUNT_EMAIL` / `PROD_BACKEND_SERVICE_ACCOUNT_EMAIL` | `backend_service_account_email` |
| `DEV_FRONTEND_SERVICE_ACCOUNT_EMAIL` / `PROD_FRONTEND_SERVICE_ACCOUNT_EMAIL` | `frontend_service_account_email` |
| `DEV_OBJECT_STORAGE_BUCKET` / `PROD_OBJECT_STORAGE_BUCKET` | `object_storage_bucket` |
| `DEV_CLOUD_SQL_DATABASE_NAME` / `PROD_CLOUD_SQL_DATABASE_NAME` | `cloud_sql_database_name` |
| `DEV_CLOUD_SQL_INSTANCE_CONNECTION_NAME` / `PROD_CLOUD_SQL_INSTANCE_CONNECTION_NAME` | `cloud_sql_instance_connection_name` |
| `DEV_GKE_CLUSTER_NAME` / `PROD_GKE_CLUSTER_NAME` | `gke_cluster_name` |
| `DEV_GKE_CLUSTER_LOCATION` / `PROD_GKE_CLUSTER_LOCATION` | `gke_cluster_location` |
| `DEV_KUBERNETES_NAMESPACE` / `PROD_KUBERNETES_NAMESPACE` | `kubernetes_namespace` |
| `DEV_RUNTIME_SECRET_NAME` / `PROD_RUNTIME_SECRET_NAME` | `runtime_secret_name` |
| `DEV_STATIC_IP_NAME` / `PROD_STATIC_IP_NAME` | `frontend_static_ip_name` |
| `DEV_STATIC_IP_ADDRESS` / `PROD_STATIC_IP_ADDRESS` | `frontend_static_ip_address` |
| `DEV_SECRET_NAMES` / `PROD_SECRET_NAMES` | `secret_names` (compact JSON containing container names only) |

## Operator inputs (hand-set)

| Variable | Purpose | Required |
| --- | --- | --- |
| `GCP_REGION` | Default region for the env roots. | yes |
| `NOTIFICATION_EMAIL` | Email that receives the dev/prod monitoring alerts. | recommended |
| `FRONTEND_EXPOSURE_MODE` | `hostname-https` (GKE-managed certificate, requires DNS) or `ip-http` (direct HTTP through the reserved static IP). | optional (default `ip-http`) |
| `FRONTEND_HOSTNAME` | Public hostname (only required when `FRONTEND_EXPOSURE_MODE=hostname-https`). | only for `hostname-https` |
| `MANAGED_CERTIFICATE_NAME` | Name of the GKE `ManagedCertificate` resource. | only for `hostname-https` |
| `DEV_OBJECT_STORAGE_BUCKET_INPUT` | Provisioning input for the dev GCS bucket name (first apply). Empty after the first apply. | yes (first apply) |
| `PROD_OBJECT_STORAGE_BUCKET_INPUT` | Provisioning input for the prod GCS bucket name (first apply). | when adding prod (first apply) |
| `DEV_STATIC_IP_NAME_INPUT` | Provisioning input for the dev static IP name (first apply). | yes (first apply) |
| `PROD_STATIC_IP_NAME_INPUT` | Provisioning input for the prod static IP name (first apply). | when adding prod (first apply) |
| `CLOUD_SQL_PROXY_IMAGE` | Cloud SQL Auth Proxy image. | optional (default `gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.15.2`) |
| `CLOUD_SQL_PROXY_PORT` | Cloud SQL Auth Proxy port. | optional (default `5432`) |
| `EXTERNAL_SECRETS_OPERATOR_VERSION` | Pinned External Secrets Operator version. | optional (default `0.10.4`) |
| `DATABASE_URL_SECRET_KEY` | Key inside the runtime Secret that holds `database-url`. | optional (default `database-url`) |
| `AUTH_SECRET_SECRET_KEY` | Key inside the runtime Secret that holds the auth secret. | optional (default `auth-secret`) |
| `DEFAULT_REPLICAS_DEV` | Backend/frontend replica count for the dev deploy. | optional (default `1`) |
| `DEFAULT_REPLICAS_PROD` | Backend/frontend replica count for the prod deploy. | optional (default `2`) |
| `FRONTEND_API_BASE_URL` | Public URL the browser uses to reach the backend. | optional |
| `FRONTEND_SERVER_API_BASE_URL` | Internal URL the Next.js server uses to reach the backend. | optional (default `http://fotosintesis-backend:8000`) |
| `MODEL_PROVIDER`, `VISION_PROVIDER`, `JUDGE_PROVIDER`, `SEARCH_PROVIDER`, `EMBEDDING_PROVIDER` | Per-role default provider. | yes (start with `mock`) |
| `MODEL_PROVIDERS`, `VISION_PROVIDERS`, `JUDGE_PROVIDERS`, `SEARCH_PROVIDERS` | Comma-separated fallback chain for each role. | optional |
| `OPENAI_TEXT_MODEL` ... `GEMINI_SEARCH_MODEL` | Provider-specific model names. | optional (defaults) |
| `EMBEDDING_DIMENSION` | Vector dimension for the embeddings table. | yes |

## Per-environment variable selection

Workflows always select the explicit dev or prod identifier from the
matching `inputs.environment`. The deploy workflow resolves
`DEV_*` and `PROD_*` repository variables to `ENV_*` step outputs and
fails fast when a required identifier is missing. The release workflow
uses `DEV_*` for source-image verification and `PROD_*` for image
promotion. The iac.yml plan/apply paths use `DEV_*` for dev operations
and `PROD_*` for prod operations. There are no generic
`TF_STATE_BUCKET`, `WIF_PROVIDER_ID`, `DEPLOY_SERVICE_ACCOUNT_EMAIL`,
`CI_SERVICE_ACCOUNT_EMAIL`, `GCP_PROJECT_ID`, or
`ARTIFACT_REGISTRY_URL` repository variables.

## Secrets

The workflow set requires exactly one GitHub Actions secret:
`FRONTEND_BUILD_AUTH_SECRET`. It is a NextAuth build-time placeholder
consumed by `frontend-ci.yml`; the runtime `AUTH_SECRET` is projected
from Secret Manager through External Secrets.

The platform does not use GitHub secrets for GCP service account keys,
API tokens, or database passwords. Runtime secret values live in GCP
Secret Manager; `gcloud secrets versions add <name> --data-file=-` is
the only supported population path.

## Sanity check

After configuring the variables, run a manual `iac.yml` dispatch with
`environment=dev` and `tofu_command=plan`. The plan should reflect the
configured variables and report `No changes` when the env root was
already applied.
