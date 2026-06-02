# Deployment And Operations

Cloud infrastructure is managed with OpenTofu in `infra/opentofu`. Kubernetes workloads are deployed with plain manifests in `deploy/k8s`. Docker Compose remains only for local development.

## Prerequisites

- OpenTofu installed as `tofu`.
- Google Cloud credentials with permission to manage GKE, Artifact Registry, Cloud SQL, Cloud Storage, Secret Manager, IAM and Cloud Monitoring.
- A GCS bucket for remote OpenTofu state.
- `gcloud` and `kubectl` installed for deployment.

## Remote State

Each environment includes `backend.tf.example`.

```bash
cd infra/opentofu/envs/dev
cp backend.tf.example backend.tf
```

Edit `backend.tf` with the state bucket and prefix for the environment. Do not commit credentials or generated state files.

## Plan And Apply

Use the environment directory you want to manage:

```bash
cd infra/opentofu/envs/dev
tofu init
tofu fmt -recursive
tofu validate
tofu plan -var-file=terraform.tfvars.example
tofu apply -var-file=terraform.tfvars.example
```

For production, use `infra/opentofu/envs/prod` and a production tfvars file. Keep production `deletion_protection = true` unless a planned teardown has been approved.

## Secrets

OpenTofu creates Secret Manager secret containers only. Secret values are intentionally not committed.

Populate values out of band, for example:

```bash
printf '%s' "$DATABASE_URL" | gcloud secrets versions add fotosintesis-database-url --data-file=-
printf '%s' "$AUTH_SECRET" | gcloud secrets versions add fotosintesis-auth-secret --data-file=-
```

The Kubernetes manifests reference a runtime Secret named `fotosintesis-runtime` by default. Create it from approved runtime values or with an External Secrets controller if one is installed. The example at `deploy/k8s/examples/runtime-secret.example.yaml` is non-applied documentation only and must not contain real secrets.

```bash
kubectl -n fotosintesis create secret generic fotosintesis-runtime \
  --from-literal=database-url="$DATABASE_URL" \
  --from-literal=auth-secret="$AUTH_SECRET"
```

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

Create an environment values file from OpenTofu outputs:

```bash
cp ../../../deploy/k8s/dev/values.env.example values.env

cat > values.env <<EOF
NAMESPACE=fotosintesis
APP_ENV=dev
IMAGE_REGISTRY=$(tofu output -raw artifact_repository_url)
BACKEND_IMAGE_TAG=latest
FRONTEND_IMAGE_TAG=latest
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
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=8
RUNTIME_SECRET_NAME=fotosintesis-runtime
EOF
```

For OpenAI embeddings, set `EMBEDDING_PROVIDER=openai`, provide `OPENAI_API_KEY`, choose
`OPENAI_EMBEDDING_MODEL`, and set `EMBEDDING_DIMENSION` to the selected model's vector size
and the existing pgvector table dimension. Changing dimensions requires rebuilding or migrating
stored vectors before rollout.

These values map to OpenTofu outputs:

- `IMAGE_REGISTRY`: `artifact_repository_url`
- `BACKEND_GCP_SERVICE_ACCOUNT_EMAIL`: `backend_service_account_email`
- `FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL`: `frontend_service_account_email`
- `OBJECT_STORAGE_BUCKET`: `object_storage_bucket`
- `CLOUD_SQL_INSTANCE_CONNECTION_NAME`: `cloud_sql_instance_connection_name`
- `CLOUD_SQL_DATABASE_NAME`: `cloud_sql_database_name`

Render manifests into an ignored directory and deploy:

```bash
sh ../../../deploy/k8s/render.sh values.env ../../../.generated/k8s/dev
kubectl apply -f ../../../.generated/k8s/dev
kubectl -n fotosintesis wait --for=condition=complete job/fotosintesis-migrations --timeout=300s
kubectl -n fotosintesis rollout status deployment/fotosintesis-backend
kubectl -n fotosintesis rollout status deployment/fotosintesis-frontend
```

If the migration Job already exists from a previous run, delete it before applying the rendered manifests again:

```bash
kubectl -n fotosintesis delete job/fotosintesis-migrations --ignore-not-found
```

## Rollback

Inspect rollout history and roll back the affected Deployment:

```bash
kubectl -n fotosintesis rollout history deployment/fotosintesis-frontend
kubectl -n fotosintesis rollout history deployment/fotosintesis-backend
kubectl -n fotosintesis rollout undo deployment/fotosintesis-frontend --to-revision=<revision>
kubectl -n fotosintesis rollout undo deployment/fotosintesis-backend --to-revision=<revision>
kubectl -n fotosintesis rollout status deployment/fotosintesis-frontend
kubectl -n fotosintesis rollout status deployment/fotosintesis-backend
```

Migration jobs are not automatically reversible. If a migration must be rolled back, restore from an approved database backup or apply a reviewed forward-fix migration, then redeploy the backend image that matches the database state.

If an infrastructure change must be rolled back, revert the OpenTofu change and run a new `tofu plan` before applying.

## Destroy Non-Production

Only destroy non-production environments after confirming data retention expectations.

```bash
cd infra/opentofu/envs/dev
kubectl delete -f ../../../.generated/k8s/dev --ignore-not-found
tofu destroy -var-file=terraform.tfvars.example
```

Production uses deletion protection by default. Disable it only through a reviewed change.
