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
    -e "s#__BACKEND_GCP_SERVICE_ACCOUNT_EMAIL__#${BACKEND_GCP_SERVICE_ACCOUNT_EMAIL}#g" \
    -e "s#__FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL__#${FRONTEND_GCP_SERVICE_ACCOUNT_EMAIL}#g" \
    -e "s#__OBJECT_STORAGE_BUCKET__#${OBJECT_STORAGE_BUCKET}#g" \
    -e "s#__CLOUD_SQL_INSTANCE_CONNECTION_NAME__#${CLOUD_SQL_INSTANCE_CONNECTION_NAME}#g" \
    -e "s#__CLOUD_SQL_DATABASE_NAME__#${CLOUD_SQL_DATABASE_NAME}#g" \
    -e "s#__PROVIDER_PROFILE__#${PROVIDER_PROFILE}#g" \
    -e "s#__RUNTIME_SECRET_NAME__#${RUNTIME_SECRET_NAME}#g" \
    "$source_file" > "$target_file"
done

printf 'Rendered manifests to %s\n' "$output_dir"
