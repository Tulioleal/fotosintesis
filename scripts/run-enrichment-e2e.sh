#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROJECT=photosynthesis-e2e
COMPOSE="docker compose -p $PROJECT -f $ROOT/docker-compose.yml -f $ROOT/docker-compose.e2e.yml"
LOCK_DIR="${TMPDIR:-/tmp}/photosynthesis-e2e.lock"

if ! mkdir "$LOCK_DIR"; then
  echo "Another photosynthesis enrichment E2E run is already active." >&2
  echo "If no run exists, remove stale lock: $LOCK_DIR" >&2
  exit 1
fi

cleanup() {
  status=$?
  trap - EXIT INT TERM
  $COMPOSE down -v --remove-orphans || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
  exit "$status"
}

trap cleanup EXIT INT TERM

$COMPOSE down -v --remove-orphans

NEXT_FONT_GOOGLE_MOCKED_RESPONSES="$ROOT/frontend/e2e/next-font-mocked-responses.cjs" \
NODE_OPTIONS="--max-old-space-size=3072" \
pnpm --dir "$ROOT" --filter frontend build

# Build the backend image up front with the host docker builder (the compose
# bake builder resolves PyPI unreliably in some environments): dependency
# installation must never run inside health-critical startup commands. Compose
# reuses this exact tag because the e2e override pins image:
# photosynthesis-backend-e2e for both backend and worker.
docker build -t photosynthesis-backend-e2e "$ROOT/backend"

$COMPOSE up -d --wait --wait-timeout 600 \
  postgres mock-gbif backend worker frontend

PLAYWRIGHT_EXTERNAL_SERVER=1 \
pnpm --dir "$ROOT" --filter frontend test:e2e:enrichment "$@"
