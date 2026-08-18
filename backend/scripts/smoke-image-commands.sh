#!/usr/bin/env sh
# Image smoke tests for the production backend commands under the fixed
# unprivileged runtime identity (UID/GID 10001:10001) and a read-only root.
#
# Every command runs with `--read-only` and a writable /tmp only, in the
# disposable PostgreSQL container's network namespace, against a real migrated
# database. The API uses the image's exact default command (its CMD); the
# worker uses the exact Kubernetes command. Both must keep running for the
# bounded interval; UID/GID 10001:10001 is asserted inside each running
# container, and logs are captured on failure. All smoke containers are always
# removed via a trap, on success or failure.
#
# Usage: sh backend/scripts/smoke-image-commands.sh <image-ref>
set -eu

IMAGE="$1"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-20}"
PG_CONTAINER="fotosintesis-smoke-pg"
PG_IMAGE="pgvector/pgvector:pg16"
API_CONTAINER="fotosintesis-smoke-api"
WORKER_CONTAINER="fotosintesis-smoke-worker"
PG_DATABASE="fotosintesis"
PG_USER="fotosintesis"
PG_PASSWORD="fotosintesis"
DATABASE_URL="postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@127.0.0.1:5432/${PG_DATABASE}"

if [ -z "$IMAGE" ]; then
  printf 'usage: %s <image-ref>\n' "$0" >&2
  exit 2
fi

cleanup() {
  docker rm -f "$API_CONTAINER" "$WORKER_CONTAINER" "$PG_CONTAINER" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf 'Starting disposable PostgreSQL (%s)\n' "$PG_IMAGE"
docker run -d --name "$PG_CONTAINER" \
  -e "POSTGRES_DB=${PG_DATABASE}" \
  -e "POSTGRES_USER=${PG_USER}" \
  -e "POSTGRES_PASSWORD=${PG_PASSWORD}" \
  "$PG_IMAGE" >/dev/null

printf 'Waiting for PostgreSQL health\n'
ready=0
for _ in $(seq 1 60); do
  if docker exec "$PG_CONTAINER" \
      pg_isready -U "$PG_USER" -d "$PG_DATABASE" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [ "$ready" != "1" ]; then
  printf 'FAIL: PostgreSQL did not become ready.\n' >&2
  docker logs "$PG_CONTAINER" >&2 || true
  exit 1
fi
printf 'PostgreSQL is ready\n'

# Common run options: read-only root, writable /tmp only, and the database
# container's network namespace so PostgreSQL is reachable at 127.0.0.1:5432.
ro() {
  printf '%s' "--read-only --tmpfs /tmp:rw,mode=1777 --network container:${PG_CONTAINER}"
}

# Migration succeeds only when `alembic upgrade head` exits zero.
printf 'Smoke: migration (alembic upgrade head)\n'
docker run --rm \
  $(ro) \
  -e "DATABASE_URL=${DATABASE_URL}" \
  "$IMAGE" sh /app/scripts/run-migrations.sh 5432
printf 'OK: migration completed\n'

# Start a container, keep it running for the bounded interval, and fail (with
# logs) if it exits early.
assert_running_bounded() {
  container="$1"
  label="$2"
  for _ in $(seq 1 "$SMOKE_TIMEOUT"); do
    state="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || true)"
    if [ "$state" != "true" ]; then
      printf 'FAIL: %s exited before the %ss bound.\n' "$label" "$SMOKE_TIMEOUT" >&2
      docker logs "$container" >&2 || true
      exit 1
    fi
    sleep 1
  done
  printf 'OK: %s remained running for the %ss bound\n' "$label" "$SMOKE_TIMEOUT"
}

# Assert the running container reports the fixed runtime identity.
assert_uid() {
  container="$1"
  label="$2"
  ids="$(docker exec "$container" sh -c 'id -u; id -g' 2>/dev/null || true)"
  uid="$(printf '%s\n' "$ids" | sed -n '1p')"
  gid="$(printf '%s\n' "$ids" | sed -n '2p')"
  if [ "$uid" != "10001" ] || [ "$gid" != "10001" ]; then
    printf 'FAIL: %s runs as %s:%s, expected 10001:10001\n' \
      "$label" "$uid" "$gid" >&2
    docker logs "$container" >&2 || true
    exit 1
  fi
  printf 'OK: %s reports UID/GID %s:%s\n' "$label" "$uid" "$gid"
}

# API: the image's exact default command (its CMD), read-only root.
printf 'Smoke: api (image default command)\n'
docker run -d --name "$API_CONTAINER" \
  $(ro) \
  -e "DATABASE_URL=${DATABASE_URL}" \
  "$IMAGE" >/dev/null
assert_running_bounded "$API_CONTAINER" "api"
assert_uid "$API_CONTAINER" "api"

# Worker: the exact Kubernetes command, read-only root.
printf 'Smoke: worker (python -m app.jobs.worker)\n'
docker run -d --name "$WORKER_CONTAINER" \
  $(ro) \
  -e "DATABASE_URL=${DATABASE_URL}" \
  "$IMAGE" python -m app.jobs.worker >/dev/null
assert_running_bounded "$WORKER_CONTAINER" "worker"
assert_uid "$WORKER_CONTAINER" "worker"

printf 'All image smoke tests passed.\n'
