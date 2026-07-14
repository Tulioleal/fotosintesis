#!/usr/bin/env sh
set -eu

if [ "$#" -ne 2 ]; then
  printf 'Usage: sh deploy/k8s/render.sh <values.env> <output-dir>\n' >&2
  exit 2
fi

values_file="$1"
output_dir="$2"
base_dir="$(CDPATH= cd -- "$(dirname -- "$0")/base" && pwd)"

set -a
. "$values_file"
set +a

# Required-value gate. The renderer cannot produce a working manifest when any
# of these is empty, so fail fast with a clear error rather than emitting a
# broken Deployment/Ingress/ExternalSecret.
required_vars="
  NAMESPACE
  APP_ENV
  IMAGE_REGISTRY
  BACKEND_IMAGE_TAG
  FRONTEND_IMAGE_TAG
  BACKEND_REPLICAS
  FRONTEND_REPLICAS
  FRONTEND_SERVICE_TYPE
  FRONTEND_API_BASE_URL
  FRONTEND_SERVER_API_BASE_URL
  BACKEND_GCP_SERVICE_ACCOUNT_EMAIL
  FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL
  OBJECT_STORAGE_PROVIDER
  OBJECT_STORAGE_BUCKET
  CLOUD_SQL_INSTANCE_CONNECTION_NAME
  CLOUD_SQL_DATABASE_NAME
  CLOUD_SQL_PROXY_IMAGE
  CLOUD_SQL_PROXY_PORT
  DATABASE_URL_SECRET_KEY
  AUTH_SECRET_SECRET_KEY
  RUNTIME_SECRET_NAME
  EXTERNAL_SECRETS_STORE_NAME
  EXTERNAL_SECRETS_REFRESH_INTERVAL
  GCP_PROJECT_ID
  MODEL_PROVIDER
  VISION_PROVIDER
  JUDGE_PROVIDER
  SEARCH_PROVIDER
  EMBEDDING_PROVIDER
  MODEL_PROVIDERS
  VISION_PROVIDERS
  JUDGE_PROVIDERS
  SEARCH_PROVIDERS
  OPENAI_TEXT_MODEL
  OPENAI_VISION_MODEL
  OPENAI_JUDGE_MODEL
  OPENAI_SEARCH_MODEL
  OPENAI_EMBEDDING_MODEL
  GEMINI_TEXT_MODEL
  GEMINI_VISION_MODEL
  GEMINI_JUDGE_MODEL
  GEMINI_SEARCH_MODEL
  EMBEDDING_DIMENSION
  STATIC_IP_NAME
  GKE_CLUSTER_PROJECT_ID
  GKE_CLUSTER_LOCATION
  GKE_CLUSTER_NAME
  AUTH_URL
 "

missing=0
for v in $required_vars; do
  eval "current=\${$v:-}"
  if [ -z "$current" ]; then
    printf 'render: required value %s is empty\n' "$v" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  printf 'render: refusing to emit manifests with missing values\n' >&2
  exit 1
fi

mkdir -p "$output_dir"

for source_file in "$base_dir"/*.yaml; do
  target_file="$output_dir/$(basename "$source_file")"
  sed \
    -e "s#__NAMESPACE__#${NAMESPACE}#g" \
    -e "s#__APP_ENV__#${APP_ENV}#g" \
    -e "s#__IMAGE_REGISTRY__#${IMAGE_REGISTRY}#g" \
    -e "s#__BACKEND_IMAGE_TAG__#${BACKEND_IMAGE_TAG}#g" \
    -e "s#__FRONTEND_IMAGE_TAG__#${FRONTEND_IMAGE_TAG}#g" \
    -e "s#__BACKEND_REPLICAS__#${BACKEND_REPLICAS}#g" \
    -e "s#__FRONTEND_REPLICAS__#${FRONTEND_REPLICAS}#g" \
    -e "s#__FRONTEND_SERVICE_TYPE__#${FRONTEND_SERVICE_TYPE}#g" \
    -e "s#__FRONTEND_API_BASE_URL__#${FRONTEND_API_BASE_URL}#g" \
    -e "s#__FRONTEND_SERVER_API_BASE_URL__#${FRONTEND_SERVER_API_BASE_URL}#g" \
    -e "s#__BACKEND_GCP_SERVICE_ACCOUNT_EMAIL__#${BACKEND_GCP_SERVICE_ACCOUNT_EMAIL}#g" \
    -e "s#__FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL__#${FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL}#g" \
    -e "s#__OBJECT_STORAGE_PROVIDER__#${OBJECT_STORAGE_PROVIDER}#g" \
    -e "s#__OBJECT_STORAGE_BUCKET__#${OBJECT_STORAGE_BUCKET}#g" \
    -e "s#__CLOUD_SQL_INSTANCE_CONNECTION_NAME__#${CLOUD_SQL_INSTANCE_CONNECTION_NAME}#g" \
    -e "s#__CLOUD_SQL_DATABASE_NAME__#${CLOUD_SQL_DATABASE_NAME}#g" \
    -e "s#__CLOUD_SQL_PROXY_IMAGE__#${CLOUD_SQL_PROXY_IMAGE}#g" \
    -e "s#__CLOUD_SQL_PROXY_PORT__#${CLOUD_SQL_PROXY_PORT}#g" \
    -e "s#__DATABASE_URL_SECRET_KEY__#${DATABASE_URL_SECRET_KEY}#g" \
    -e "s#__AUTH_SECRET_SECRET_KEY__#${AUTH_SECRET_SECRET_KEY}#g" \
    -e "s#__MODEL_PROVIDER__#${MODEL_PROVIDER}#g" \
    -e "s#__VISION_PROVIDER__#${VISION_PROVIDER}#g" \
    -e "s#__JUDGE_PROVIDER__#${JUDGE_PROVIDER}#g" \
    -e "s#__SEARCH_PROVIDER__#${SEARCH_PROVIDER}#g" \
    -e "s#__EMBEDDING_PROVIDER__#${EMBEDDING_PROVIDER}#g" \
    -e "s#__MODEL_PROVIDERS__#${MODEL_PROVIDERS}#g" \
    -e "s#__VISION_PROVIDERS__#${VISION_PROVIDERS}#g" \
    -e "s#__JUDGE_PROVIDERS__#${JUDGE_PROVIDERS}#g" \
    -e "s#__SEARCH_PROVIDERS__#${SEARCH_PROVIDERS}#g" \
    -e "s#__OPENAI_TEXT_MODEL__#${OPENAI_TEXT_MODEL}#g" \
    -e "s#__OPENAI_VISION_MODEL__#${OPENAI_VISION_MODEL}#g" \
    -e "s#__OPENAI_JUDGE_MODEL__#${OPENAI_JUDGE_MODEL}#g" \
    -e "s#__OPENAI_SEARCH_MODEL__#${OPENAI_SEARCH_MODEL}#g" \
    -e "s#__OPENAI_EMBEDDING_MODEL__#${OPENAI_EMBEDDING_MODEL}#g" \
    -e "s#__GEMINI_TEXT_MODEL__#${GEMINI_TEXT_MODEL}#g" \
    -e "s#__GEMINI_VISION_MODEL__#${GEMINI_VISION_MODEL}#g" \
    -e "s#__GEMINI_JUDGE_MODEL__#${GEMINI_JUDGE_MODEL}#g" \
    -e "s#__GEMINI_SEARCH_MODEL__#${GEMINI_SEARCH_MODEL}#g" \
    -e "s#__EMBEDDING_DIMENSION__#${EMBEDDING_DIMENSION}#g" \
    -e "s#__RUNTIME_SECRET_NAME__#${RUNTIME_SECRET_NAME}#g" \
    -e "s#__EXTERNAL_SECRETS_STORE_NAME__#${EXTERNAL_SECRETS_STORE_NAME}#g" \
    -e "s#__EXTERNAL_SECRETS_REFRESH_INTERVAL__#${EXTERNAL_SECRETS_REFRESH_INTERVAL}#g" \
    -e "s#__GCP_PROJECT_ID__#${GCP_PROJECT_ID}#g" \
    -e "s#__STATIC_IP_NAME__#${STATIC_IP_NAME}#g" \
    -e "s#__GKE_CLUSTER_PROJECT_ID__#${GKE_CLUSTER_PROJECT_ID}#g" \
    -e "s#__GKE_CLUSTER_LOCATION__#${GKE_CLUSTER_LOCATION}#g" \
    -e "s#__GKE_CLUSTER_NAME__#${GKE_CLUSTER_NAME}#g" \
    -e "s#__FRONTEND_HOSTNAME__#${FRONTEND_HOSTNAME}#g" \
    -e "s#__MANAGED_CERTIFICATE_NAME__#${MANAGED_CERTIFICATE_NAME}#g" \
    -e "s#__AUTH_URL__#${AUTH_URL}#g" \
    "$source_file" > "$target_file"
done

printf 'Rendered manifests to %s\n' "$output_dir"
