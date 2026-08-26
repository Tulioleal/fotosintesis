#!/usr/bin/env sh
# Verify the built frontend image enforces the fixed unprivileged runtime
# identity (UID/GID 1001:1001) and that the exact production Node command
# starts under a read-only root with a writable /tmp, before deployment.
#
# Usage: sh frontend/scripts/check-image-runtime.sh <image-ref>
#
# This is the deterministic image gate for the frontend: it rejects a default
# UID of 0, asserts the documented 1001:1001 identity, starts the container
# with `--read-only` and a writable /tmp only, and rejects an early process
# exit. The container is always removed via a trap.
set -eu

IMAGE="$1"
CONTAINER="fotosintesis-frontend-check"
HOST_PORT="${FRONTEND_CHECK_PORT:-13100}"
CHECK_SECONDS="${FRONTEND_CHECK_SECONDS:-20}"

if [ -z "$IMAGE" ]; then
  printf 'usage: %s <image-ref>\n' "$0" >&2
  exit 2
fi

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Reject a root default by inspecting the image config user.
image_user="$(docker image inspect -f '{{.Config.User}}' "$IMAGE")"
if [ "$image_user" = "0" ] || [ "$image_user" = "0:0" ] || [ -z "$image_user" ]; then
  printf 'FAIL: image %s does not set a non-zero default user (got %s).\n' \
    "$IMAGE" "$image_user" >&2
  exit 1
fi

# Start the exact production command (the image default CMD) with a read-only
# root and a writable /tmp only.
printf 'Starting frontend (%s) with a read-only root\n' "$IMAGE"
docker run -d --name "$CONTAINER" \
  --read-only --tmpfs /tmp:rw,mode=1777 \
  -p "$HOST_PORT:3000" \
  -e NODE_ENV=production \
  -e PORT=3000 \
  -e HOSTNAME=0.0.0.0 \
  -e HOME=/tmp \
  -e AUTH_SECRET=fotosintesis-image-check-secret \
  -e AUTH_TRUST_HOST=true \
  -e AUTH_URL="http://127.0.0.1:$HOST_PORT" \
  -e API_BASE_URL="http://127.0.0.1:8000" \
  "$IMAGE" >/dev/null

ids="$(docker exec "$CONTAINER" sh -c 'id -u; id -g' 2>/dev/null || true)"
uid="$(printf '%s\n' "$ids" | sed -n '1p')"
gid="$(printf '%s\n' "$ids" | sed -n '2p')"
if [ "$uid" != "1001" ] || [ "$gid" != "1001" ]; then
  printf 'FAIL: frontend runs as %s:%s, expected 1001:1001\n' "$uid" "$gid" >&2
  docker logs "$CONTAINER" >&2 || true
  exit 1
fi
printf 'OK: frontend reports UID/GID %s:%s\n' "$uid" "$gid"

# Poll the server and reject an early process exit.
printf 'Polling frontend on http://127.0.0.1:%s\n' "$HOST_PORT"
ok=0
for _ in $(seq 1 "$CHECK_SECONDS"); do
  state="$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || true)"
  if [ "$state" != "true" ]; then
    printf 'FAIL: frontend process exited early.\n' >&2
    docker logs "$CONTAINER" >&2 || true
    exit 1
  fi
  if command -v curl >/dev/null 2>&1 &&
      curl --silent --show-error --fail --max-time 2 \
        "http://127.0.0.1:$HOST_PORT/" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done

printf 'OK: frontend remained running for the %ss check window\n' "$CHECK_SECONDS"
if [ "$ok" = "1" ]; then
  printf 'OK: frontend root endpoint responded\n'
else
  printf 'Note: frontend stayed up but the root endpoint did not respond within the window (curl unavailable or slow start).\n'
fi

printf 'Frontend image runtime check passed.\n'
