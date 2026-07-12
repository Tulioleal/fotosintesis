# Environment Contract (OpenTofu Outputs)

The deploy and release workflows read the following OpenTofu outputs
from the env roots (`infra/opentofu/envs/{dev,prod}`). The deploy
workflow refuses to render manifests when any of them is missing.

## Runtime outputs

| Output | Description | Example |
| --- | --- | --- |
| `artifact_repository_url` | Fully-qualified Artifact Registry URL. | `us-central1-docker.pkg.dev/fotosintesis-prod/fotosintesis` |
| `gke_cluster_name` | GKE cluster name. | `fotosintesis-prod` |
| `gke_cluster_location` | GKE cluster region. | `us-central1` |
| `kubernetes_namespace` | Namespace the deploy workflow uses for every `kubectl` call. | `fotosintesis` |
| `project_id` | GCP project ID. | `fotosintesis-prod` |
| `backend_service_account_email` | Workload Identity service account for the backend. | `fotosintesis-backend-prod@fotosintesis-prod.iam.gserviceaccount.com` |
| `frontend_service_account_email` | Workload Identity service account for the frontend. | `fotosintesis-frontend-prod@fotosintesis-prod.iam.gserviceaccount.com` |
| `object_storage_bucket` | Application GCS bucket. | `fotosintesis-prod-storage` |
| `cloud_sql_instance_connection_name` | Cloud SQL connection name (used by the proxy). | `fotosintesis-prod:us-central1:fotosintesis-prod-postgres` |
| `cloud_sql_database_name` | Application database name. | `fotosintesis` |
| `frontend_static_ip_name` | Name of the reserved global static IP. | `fotosintesis-prod-frontend-ip` |
| `frontend_static_ip_address` | IPv4 address of the reserved static IP. | `34.117.45.67` |
| `secret_names` | Map of Secret Manager container names. The iac.yml post-apply sync job publishes it as a compact JSON object (container names only, never values). | `{ database-url = "...", auth-secret = "...", ... }` |
| `runtime_secret_name` | Name of the Kubernetes Secret projected by External Secrets. | `fotosintesis-runtime` |

The iac.yml post-apply sync jobs publish the per-environment
synchronized values to repository variables prefixed with `DEV_` or
`PROD_`:

- `DEV_ARTIFACT_REGISTRY_URL` / `PROD_ARTIFACT_REGISTRY_URL`
- `DEV_BACKEND_SERVICE_ACCOUNT_EMAIL` / `PROD_BACKEND_SERVICE_ACCOUNT_EMAIL`
- `DEV_FRONTEND_SERVICE_ACCOUNT_EMAIL` / `PROD_FRONTEND_SERVICE_ACCOUNT_EMAIL`
- `DEV_OBJECT_STORAGE_BUCKET` / `PROD_OBJECT_STORAGE_BUCKET`
- `DEV_CLOUD_SQL_DATABASE_NAME` / `PROD_CLOUD_SQL_DATABASE_NAME`
- `DEV_CLOUD_SQL_INSTANCE_CONNECTION_NAME` / `PROD_CLOUD_SQL_INSTANCE_CONNECTION_NAME`
- `DEV_GKE_CLUSTER_NAME` / `PROD_GKE_CLUSTER_NAME`
- `DEV_GKE_CLUSTER_LOCATION` / `PROD_GKE_CLUSTER_LOCATION`
- `DEV_KUBERNETES_NAMESPACE` / `PROD_KUBERNETES_NAMESPACE`
- `DEV_RUNTIME_SECRET_NAME` / `PROD_RUNTIME_SECRET_NAME`
- `DEV_STATIC_IP_NAME` / `PROD_STATIC_IP_NAME`
- `DEV_STATIC_IP_ADDRESS` / `PROD_STATIC_IP_ADDRESS`
- `DEV_SECRET_NAMES` / `PROD_SECRET_NAMES` (compact JSON, container names only)

The sync jobs use a fixed allow-list of non-sensitive outputs, reject
anything marked sensitive, and never echo the output JSON to logs. They
write repository variables with the `ACTIONS_VARIABLES_TOKEN` repository
secret, which must be a fine-grained PAT with repository Variables write
permission. They only run after a successful apply (auto-apply on main
for dev, manual apply for dev or prod).

## Foundation outputs (from bootstrap)

The bootstrap root publishes the following to GitHub repository
variables through the GitHub provider. The iac.yml post-apply sync
jobs own the per-environment outputs; bootstrap owns only this
foundation-variable namespace.

| Foundation variable | Source |
| --- | --- |
| `DEV_TF_STATE_BUCKET` / `PROD_TF_STATE_BUCKET` | bootstrap state bucket modules |
| `DEV_WIF_PROVIDER_ID` / `PROD_WIF_PROVIDER_ID` | bootstrap Workload Identity modules |
| `DEV_CI_SERVICE_ACCOUNT_EMAIL` / `PROD_CI_SERVICE_ACCOUNT_EMAIL` | bootstrap-iam CI accounts |
| `DEV_DEPLOY_SERVICE_ACCOUNT_EMAIL` / `PROD_DEPLOY_SERVICE_ACCOUNT_EMAIL` | bootstrap-iam deploy accounts |
| `DEV_IAC_SERVICE_ACCOUNT_EMAIL` / `PROD_IAC_SERVICE_ACCOUNT_EMAIL` | bootstrap-iam IaC accounts |
| `DEV_GCP_PROJECT_ID` / `PROD_GCP_PROJECT_ID` | bootstrap input variables |
| `DEV_GCP_PROJECT_NUMBER` / `PROD_GCP_PROJECT_NUMBER` | bootstrap input variables |
| `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL` | bootstrap prod CI service-account email |

## Per-environment inputs

The OpenTofu env roots accept these variables. Most of them have safe
defaults in `variables.tf`; the operator-supplied values are mapped
from repository variables through `iac.yml`.

| Variable | Used for |
| --- | --- |
| `project_id` | Provider project, all module inputs. |
| `region` | GKE, Artifact Registry, Cloud SQL region. |
| `gke_location` | Optional GKE location override. Dev workflows default to `us-central1-a` to keep dev zonal and reduce SSD quota pressure. Set explicitly for prod if a non-regional location is desired. |
| `artifact_repository_id` | Artifact Registry repository name. |
| `cluster_name` | GKE cluster name. |
| `database_instance_name` | Cloud SQL instance name. |
| `database_name` | Application database name. |
| `object_storage_bucket` | Application GCS bucket name. Operators override on the first apply through `TF_VAR_object_storage_bucket` (from `DEV_OBJECT_STORAGE_BUCKET_INPUT` / `PROD_OBJECT_STORAGE_BUCKET_INPUT`). Empty after the first apply so the env root keeps its default. |
| `frontend_static_ip_name` | Reserved static IP name. Operators override on the first apply through `TF_VAR_frontend_static_ip_name` (from `DEV_STATIC_IP_NAME_INPUT` / `PROD_STATIC_IP_NAME_INPUT`). Empty after the first apply. |
| `prod_promotion_service_account_email` | (dev root only) Email of the prod CI service account that gets `roles/artifactregistry.reader` on the dev project. Bootstrap publishes this as `DEV_PROD_PROMOTION_SERVICE_ACCOUNT_EMAIL`; `iac.yml` maps it to `TF_VAR_prod_promotion_service_account_email`. Empty disables the binding. |
| `secret_ids` | Set of Secret Manager container IDs. The env roots create the four containers required by `80-external-secrets.yaml`: `fotosintesis-database-url`, `fotosintesis-auth-secret`, `fotosintesis-openai-api-key`, `fotosintesis-gemini-api-key`. The legacy `fotosintesis-object-storage-access-key`, `fotosintesis-object-storage-secret-key`, and `fotosintesis-provider-api-keys` containers are no longer created; GKE uses Workload Identity for GCS access. |
| `kubernetes_namespace` | Kubernetes namespace for the runtime. |
| `notification_email` | Optional. Email for the GKE CPU alert. |

## Provider configuration

The deploy workflow reads provider defaults from repository variables,
not from OpenTofu outputs. The values flow into the rendered
`20-config.yaml` ConfigMap and from there into the backend Deployment
environment.

The `Verify required provider API key secrets` step iterates the
configured provider family (`MODEL_PROVIDERS`, `VISION_PROVIDERS`,
`JUDGE_PROVIDERS`, `SEARCH_PROVIDERS`) and checks that each
non-`mock` provider has a corresponding key in the runtime Secret
(`openai-api-key` for `openai`, `gemini-api-key` for `gemini`). The
deploy fails when a configured provider is missing its key.
