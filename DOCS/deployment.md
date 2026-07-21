# Deployment And Operations

Cloud infrastructure is managed with OpenTofu in `infra/opentofu`. Kubernetes workloads are deployed with plain manifests in `deploy/k8s`. Docker Compose remains only for local development.

The deployment platform splits state into three roots: `infra/opentofu/bootstrap` (local-operator-only, local-state-only, foundation trust path) and `infra/opentofu/envs/{dev,prod}` (remote-state, applied through GitHub Actions). The bootstrap root is the only OpenTofu apply a human runs; the env roots are applied through GitHub Actions under OIDC.

The foundation GitHub repository variables (state buckets, project IDs, CI/deploy/IaC service-account emails, WIF provider IDs) are published by the bootstrap root through the GitHub provider. The per-environment output variables (artifact registry URLs, Cloud SQL connection names, GKE cluster info, runtime secret name) are published by `iac.yml` post-apply sync jobs. Operators set only provisioning inputs and runtime configuration.

## Prerequisites

- OpenTofu installed as `tofu` (`>= 1.8.0`).
- Google Cloud credentials with permission to manage GKE, Artifact Registry, Cloud SQL, Cloud Storage, Secret Manager, IAM and Cloud Monitoring.
- `gcloud` and `kubectl` installed for local development and troubleshooting.
- A fine-grained GitHub personal access token scoped to the target repository with **Actions variables: Write** for the bootstrap root. Export it as `GITHUB_TOKEN` before running `tofu apply` against the bootstrap root. The token never lands in `terraform.tfvars`, OpenTofu outputs, or state.

## Bootstrap

The `infra/opentofu/bootstrap` root is applied once by a human operator from a workstation with administrator credentials. It owns the dev/prod state buckets, the Workload Identity pool/providers, the per-project CI/deploy/IaC service accounts, and the foundation GitHub repository variables. Bootstrap state is local; there is no `backend` block and no migration.

```bash
gcloud auth application-default login
gcloud config set project "$DEV_PROJECT_ID"
export GITHUB_TOKEN="<fine-grained PAT with Actions variables: Write>"

cd infra/opentofu/bootstrap
tofu init
tofu fmt -recursive
tofu validate
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars
```

Subsequent `tofu plan/apply` for the bootstrap root is idempotent. Keep `terraform.tfstate` (and `terraform.tfstate.backup`) in a private, backed-up directory on the operator workstation.

## Remote State (env roots)

Each environment root declares `backend "gcs" {}`. Bucket and prefix are
supplied at init time via `-backend-config`. The env roots are applied
through `iac.yml` under OIDC. The dev plan/apply path authenticates as
`DEV_IAC_SERVICE_ACCOUNT_EMAIL`; the prod manual apply path authenticates
as `PROD_IAC_SERVICE_ACCOUNT_EMAIL`. After a successful apply, `iac.yml`
post-apply sync jobs publish the per-environment outputs to repository
variables. The sync jobs use a fixed allow-list of non-sensitive outputs,
reject anything marked sensitive, never echo the output JSON to logs, and
write repository variables with the `ACTIONS_VARIABLES_TOKEN` repository
secret, which must be a fine-grained PAT with repository Variables write
permission.

Local debugging example for dev:

```bash
cd infra/opentofu/envs/dev
tofu init \
  -backend-config="bucket=${DEV_TF_STATE_BUCKET}" \
  -backend-config="prefix=fotosintesis/dev"
```

Do not commit credentials or generated state files.

## Plan And Apply

The recommended way to apply each env root is through `iac.yml`. Operators can also drive the env roots from a workstation with `gcloud` for first-time debugging:

```bash
cd infra/opentofu/envs/dev
tofu init
tofu fmt -recursive
tofu validate
tofu plan -var-file=terraform.tfvars
tofu apply -var-file=terraform.tfvars
```

For production, use `infra/opentofu/envs/prod` and a production tfvars file. Keep production `deletion_protection = true` unless a planned teardown has been approved.

## Secrets

OpenTofu creates Secret Manager secret containers only. The `secret_ids` default in `infra/opentofu/envs/{dev,prod}/variables.tf` is the four containers required by `deploy/k8s/base/80-external-secrets.yaml`: `fotosintesis-database-url`, `fotosintesis-auth-secret`, `fotosintesis-openai-api-key`, and `fotosintesis-gemini-api-key`. The legacy `fotosintesis-object-storage-access-key`, `fotosintesis-object-storage-secret-key`, and `fotosintesis-provider-api-keys` containers are no longer created; GKE access to GCS uses Workload Identity.

Populate values out of band, for example:

```bash
printf '%s' "$DATABASE_URL" | gcloud secrets versions add fotosintesis-database-url \
  --project="$PROJECT_ID" --data-file=-
printf '%s' "$AUTH_SECRET" | gcloud secrets versions add fotosintesis-auth-secret \
  --project="$PROJECT_ID" --data-file=-
printf '%s' "$OPENAI_API_KEY" | gcloud secrets versions add fotosintesis-openai-api-key \
  --project="$PROJECT_ID" --data-file=-
printf '%s' "$GEMINI_API_KEY" | gcloud secrets versions add fotosintesis-gemini-api-key \
  --project="$PROJECT_ID" --data-file=-
```

The Kubernetes manifests reference a runtime Secret named `fotosintesis-runtime` by default. The `deploy.yml` workflow installs the External Secrets Operator and projects the Secret Manager values into the cluster through the `SecretStore` and `ExternalSecret` resources in `80-external-secrets.yaml`. The example at `deploy/k8s/examples/runtime-secret.example.yaml` is non-applied documentation only and must not contain real secrets.

## Deploy To GKE

Connect to the cluster from OpenTofu outputs:

```bash
cd infra/opentofu/envs/dev
gcloud container clusters get-credentials "$(tofu output -raw gke_cluster_name)" \
  --region "$(tofu output -raw gke_cluster_location)"
```

Build and push images to the Artifact Registry output:

```bash
REGISTRY="$(tofu output -raw artifact_repository_url)"
docker build -t "$REGISTRY/backend:latest" backend
docker build -t "$REGISTRY/frontend:latest" frontend
docker push "$REGISTRY/backend:latest"
docker push "$REGISTRY/frontend:latest"
```

The CI workflows (`backend-ci.yml`, `frontend-ci.yml`) build and push the images with a 40-character Git commit SHA tag, not `latest`. They authenticate as `DEV_CI_SERVICE_ACCOUNT_EMAIL` through the dev WIF provider.

Create an environment values file from OpenTofu outputs:

```bash
cp ../../../deploy/k8s/dev/values.env.example values.env

cat > values.env <<EOF
NAMESPACE=fotosintesis
APP_ENV=dev
IMAGE_REGISTRY=$(tofu output -raw artifact_repository_url)
BACKEND_IMAGE_TAG=<40-character-git-sha>
FRONTEND_IMAGE_TAG=<40-character-git-sha>
BACKEND_REPLICAS=1
FRONTEND_REPLICAS=1
FRONTEND_SERVICE_TYPE=ClusterIP
FRONTEND_API_BASE_URL=http://fotosintesis-backend:8000
BACKEND_GCP_SERVICE_ACCOUNT_EMAIL=$(tofu output -raw backend_service_account_email)
FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL=$(tofu output -raw frontend_service_account_email)
OBJECT_STORAGE_BUCKET=$(tofu output -raw object_storage_bucket)
CLOUD_SQL_INSTANCE_CONNECTION_NAME=$(tofu output -raw cloud_sql_instance_connection_name)
CLOUD_SQL_DATABASE_NAME=$(tofu output -raw cloud_sql_database_name)
MODEL_PROVIDER=mock
VISION_PROVIDER=mock
JUDGE_PROVIDER=mock
SEARCH_PROVIDER=mock
EMBEDDING_PROVIDER=mock
OPENAI_TEXT_MODEL=gpt-5.4
OPENAI_VISION_MODEL=gpt-5.4
OPENAI_JUDGE_MODEL=gpt-5.4
OPENAI_SEARCH_MODEL=gpt-5.4
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
GEMINI_TEXT_MODEL=gemini-2.5-flash
GEMINI_VISION_MODEL=gemini-2.5-flash
GEMINI_JUDGE_MODEL=gemini-2.5-flash
GEMINI_SEARCH_MODEL=gemini-2.5-flash
EMBEDDING_DIMENSION=8
RUNTIME_SECRET_NAME=fotosintesis-runtime
JOBS_PRODUCER_ENABLED=false
JOBS_WORKER_ENABLED=true
JOBS_POLL_INTERVAL_SECONDS=5
JOBS_BATCH_SIZE=10
JOBS_WORKER_CONCURRENCY=5
JOBS_LEASE_DURATION_SECONDS=300
JOBS_LEASE_RENEWAL_INTERVAL_SECONDS=60
JOBS_MAX_ATTEMPTS_DEFAULT=3
JOBS_BACKOFF_BASE_SECONDS=10
JOBS_BACKOFF_CAP_SECONDS=3600
JOBS_SHUTDOWN_DRAIN_SECONDS=30
JOBS_METRICS_HOST=0.0.0.0
JOBS_METRICS_PORT=9100
JOBS_TERMINATION_GRACE_PERIOD_SECONDS=90
EOF
```

For OpenAI embeddings, set `EMBEDDING_PROVIDER=openai`, provide `OPENAI_API_KEY`, choose
`OPENAI_EMBEDDING_MODEL`, and set `EMBEDDING_DIMENSION` to the selected model's vector size
and the existing pgvector table dimension. Changing dimensions requires rebuilding or migrating
stored vectors before rollout.

To run Gemini for all non-embedding AI roles, keep embeddings on OpenAI and configure:

```env
MODEL_PROVIDER=gemini
VISION_PROVIDER=gemini
JUDGE_PROVIDER=gemini
SEARCH_PROVIDER=gemini
EMBEDDING_PROVIDER=openai
GEMINI_TEXT_MODEL=gemini-2.5-flash
GEMINI_VISION_MODEL=gemini-2.5-flash
GEMINI_JUDGE_MODEL=gemini-2.5-flash
GEMINI_SEARCH_MODEL=gemini-2.5-flash
```

This runtime requires `GEMINI_API_KEY` for Gemini model, vision, judge and search roles, plus
`OPENAI_API_KEY` for OpenAI embeddings. `SEARCH_PROVIDER=gemini` uses Gemini Google Search
grounding and should be smoke-tested with a real `/health` request and an `/assistant/chat`
question that requires live botanical evidence before production rollout.

These values map to OpenTofu outputs:

- `IMAGE_REGISTRY`: `artifact_repository_url`
- `BACKEND_GCP_SERVICE_ACCOUNT_EMAIL`: `backend_service_account_email`
- `FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL`: `frontend_service_account_email`
- `OBJECT_STORAGE_BUCKET`: `object_storage_bucket`
- `CLOUD_SQL_INSTANCE_CONNECTION_NAME`: `cloud_sql_instance_connection_name`
- `CLOUD_SQL_DATABASE_NAME`: `cloud_sql_database_name`

Render manifests into an ignored directory. Apply prerequisites first, then the
migration Job by itself. Do not apply the whole rendered directory: doing so can
start a new API or worker before its schema exists.

```bash
sh ../../../deploy/k8s/render.sh values.env ../../../.generated/k8s/dev
RENDERED=../../../.generated/k8s/dev

kubectl apply -f "$RENDERED/00-namespace.yaml"
kubectl apply -f "$RENDERED/10-service-accounts.yaml"
kubectl apply -f "$RENDERED/20-config.yaml"
kubectl apply -f "$RENDERED/80-external-secrets.yaml"

kubectl -n fotosintesis delete job/fotosintesis-migrations --ignore-not-found
kubectl apply -f "$RENDERED/50-migrations.yaml"
kubectl -n fotosintesis wait --for=condition=complete \
  job/fotosintesis-migrations --timeout=600s

kubectl apply -f "$RENDERED/30-backend.yaml"
kubectl apply -f "$RENDERED/55-worker.yaml"
kubectl apply -f "$RENDERED/40-frontend.yaml"
kubectl apply -f "$RENDERED/70-ingress.yaml"
# Apply 60-managed-certificate.yaml only in hostname-https mode.

sh ../../../deploy/scripts/rollout-deployment.sh \
  fotosintesis fotosintesis-backend backend 600s
sh ../../../deploy/scripts/rollout-deployment.sh \
  fotosintesis fotosintesis-worker worker 600s
sh ../../../deploy/scripts/rollout-deployment.sh \
  fotosintesis fotosintesis-frontend frontend 600s
```

Wait for the ExternalSecret to project the runtime Secret before applying the
migration. The GitHub deploy workflow performs that wait and the provider-key
gate automatically. It records the last-healthy image pair only after migration,
all three rollouts, and smoke checks pass; a worker rollout failure therefore
cannot be recorded as healthy.

## Rollback

Inspect rollout history and roll back the affected Deployment:

```bash
kubectl rollout history deployment/fotosintesis-worker -n "$NAMESPACE"
kubectl rollout history deployment/fotosintesis-frontend -n "$NAMESPACE"
kubectl rollout history deployment/fotosintesis-backend -n "$NAMESPACE"
kubectl rollout undo deployment/fotosintesis-worker -n "$NAMESPACE"
kubectl rollout undo deployment/fotosintesis-frontend -n "$NAMESPACE" --to-revision=<revision>
kubectl rollout undo deployment/fotosintesis-backend -n "$NAMESPACE" --to-revision=<revision>
kubectl rollout status deployment/fotosintesis-worker -n "$NAMESPACE" --timeout=600s
kubectl rollout status deployment/fotosintesis-frontend -n "$NAMESPACE"
kubectl rollout status deployment/fotosintesis-backend -n "$NAMESPACE"
```

Migration jobs are not automatically reversible. If a migration must be rolled back, restore from an approved database backup or apply a reviewed forward-fix migration, then redeploy the backend image that matches the database state.

The backend API and worker use the same immutable backend SHA and must remain
compatible with the schema and all persisted payload versions still in flight.
Disable `JOBS_PRODUCER_ENABLED` to stop new jobs independently from
`JOBS_WORKER_ENABLED`; do not restore the former in-memory ingestion path.

If an infrastructure change must be rolled back, revert the OpenTofu change and run a new `tofu plan` before applying.

## Destroy Non-Production

Only destroy non-production environments after confirming data retention expectations.

```bash
cd infra/opentofu/envs/dev
kubectl delete -f ../../../.generated/k8s/dev --ignore-not-found
tofu destroy -var-file=terraform.tfvars.example
```

Production uses deletion protection by default. Disable it only through a reviewed change.
