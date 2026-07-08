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
| `secret_names` | Map of Secret Manager container names. | `{ database-url = "...", auth-secret = "...", ... }` |
| `runtime_secret_name` | Name of the Kubernetes Secret projected by External Secrets. | `fotosintesis-runtime` |

## Foundation outputs (from bootstrap)

The following are produced by `infra/opentofu/bootstrap`. They are
mapped to GitHub repository/environment variables, not consumed
directly by the deploy workflow.

| Output | Maps to |
| --- | --- |
| `dev_state_bucket` / `prod_state_bucket` | `TF_STATE_BUCKET` per environment. |
| `dev_wif_provider_id` / `prod_wif_provider_id` | `WIF_PROVIDER_ID` per environment. |
| `dev_ci_service_account_email` / `prod_ci_service_account_email` | `DEV_CI_SERVICE_ACCOUNT_EMAIL` / `PROD_CI_SERVICE_ACCOUNT_EMAIL`. |
| `dev_deploy_service_account_email` / `prod_deploy_service_account_email` | `DEPLOY_SERVICE_ACCOUNT_EMAIL` per environment. |
| `dev_project_id` / `prod_project_id` | `DEV_GCP_PROJECT_ID` / `PROD_GCP_PROJECT_ID`. |
| `dev_project_number` / `prod_project_number` | Used by the dev OpenTofu root to construct the cross-project reader binding. |

## Per-environment inputs

The OpenTofu env roots accept these variables. Most of them have safe
defaults in `variables.tf`; the operator-supplied values are mapped
from repository variables through `iac.yml`.

| Variable | Used for |
| --- | --- |
| `project_id` | Provider project, all module inputs. |
| `region` | GKE, Artifact Registry, Cloud SQL region. |
| `artifact_repository_id` | Artifact Registry repository name. |
| `cluster_name` | GKE cluster name. |
| `database_instance_name` | Cloud SQL instance name. |
| `database_name` | Application database name. |
| `object_storage_bucket` | Application GCS bucket name. |
| `frontend_static_ip_name` | Reserved static IP name. |
| `prod_promotion_service_account_email` | (dev root only) Email of the prod CI service account that gets `roles/artifactregistry.reader` on the dev project. Empty disables the binding. |
| `secret_ids` | Set of Secret Manager container IDs. |
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
non-`mock` provider has a corresponding key in the runtime Secret.
The deploy fails when a configured provider is missing its key.
