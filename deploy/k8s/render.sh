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
  JOBS_PRODUCER_ENABLED
  JOBS_WORKER_ENABLED
  JOBS_POLL_INTERVAL_SECONDS
  JOBS_BATCH_SIZE
  JOBS_WORKER_CONCURRENCY
  JOBS_LEASE_DURATION_SECONDS
  JOBS_LEASE_RENEWAL_INTERVAL_SECONDS
  JOBS_MAX_ATTEMPTS_DEFAULT
  JOBS_BACKOFF_BASE_SECONDS
  JOBS_BACKOFF_CAP_SECONDS
  JOBS_SHUTDOWN_DRAIN_SECONDS
  JOBS_METRICS_HOST
  JOBS_METRICS_PORT
  JOBS_TERMINATION_GRACE_PERIOD_SECONDS
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

case "$JOBS_SHUTDOWN_DRAIN_SECONDS" in
  ''|*[!0-9]*)
    printf 'render: JOBS_SHUTDOWN_DRAIN_SECONDS must be an integer\n' >&2
    exit 1
    ;;
esac

case "$JOBS_TERMINATION_GRACE_PERIOD_SECONDS" in
  ''|*[!0-9]*)
    printf 'render: JOBS_TERMINATION_GRACE_PERIOD_SECONDS must be an integer\n' >&2
    exit 1
    ;;
esac

if [ "$JOBS_TERMINATION_GRACE_PERIOD_SECONDS" -le "$JOBS_SHUTDOWN_DRAIN_SECONDS" ]; then
  printf '%s\n' 'render: termination grace must exceed worker shutdown drain timeout' >&2
  exit 1
fi

validate_sha40() {
  label="$1"
  value="$2"

  if [ "${#value}" -ne 40 ]; then
    printf \
      'render: %s must be a 40-character lowercase hexadecimal Git SHA\n' \
      "$label" >&2
    exit 1
  fi

  case "$value" in
    *[!0-9a-f]*)
      printf \
        'render: %s must be a 40-character lowercase hexadecimal Git SHA\n' \
        "$label" >&2
      exit 1
      ;;
  esac
}

validate_sha40 BACKEND_IMAGE_TAG "$BACKEND_IMAGE_TAG"
validate_sha40 FRONTEND_IMAGE_TAG "$FRONTEND_IMAGE_TAG"

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
    -e "s#__JOBS_PRODUCER_ENABLED__#${JOBS_PRODUCER_ENABLED}#g" \
    -e "s#__JOBS_WORKER_ENABLED__#${JOBS_WORKER_ENABLED}#g" \
    -e "s#__JOBS_POLL_INTERVAL_SECONDS__#${JOBS_POLL_INTERVAL_SECONDS}#g" \
    -e "s#__JOBS_BATCH_SIZE__#${JOBS_BATCH_SIZE}#g" \
    -e "s#__JOBS_WORKER_CONCURRENCY__#${JOBS_WORKER_CONCURRENCY}#g" \
    -e "s#__JOBS_LEASE_DURATION_SECONDS__#${JOBS_LEASE_DURATION_SECONDS}#g" \
    -e "s#__JOBS_LEASE_RENEWAL_INTERVAL_SECONDS__#${JOBS_LEASE_RENEWAL_INTERVAL_SECONDS}#g" \
    -e "s#__JOBS_MAX_ATTEMPTS_DEFAULT__#${JOBS_MAX_ATTEMPTS_DEFAULT}#g" \
    -e "s#__JOBS_BACKOFF_BASE_SECONDS__#${JOBS_BACKOFF_BASE_SECONDS}#g" \
    -e "s#__JOBS_BACKOFF_CAP_SECONDS__#${JOBS_BACKOFF_CAP_SECONDS}#g" \
    -e "s#__JOBS_SHUTDOWN_DRAIN_SECONDS__#${JOBS_SHUTDOWN_DRAIN_SECONDS}#g" \
    -e "s#__JOBS_METRICS_HOST__#${JOBS_METRICS_HOST}#g" \
    -e "s#__JOBS_METRICS_PORT__#${JOBS_METRICS_PORT}#g" \
    -e "s#__JOBS_TERMINATION_GRACE_PERIOD_SECONDS__#${JOBS_TERMINATION_GRACE_PERIOD_SECONDS}#g" \
    "$source_file" > "$target_file"
done

printf 'Rendered manifests to %s\n' "$output_dir"
