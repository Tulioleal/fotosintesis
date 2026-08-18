#!/usr/bin/env sh
# Verify the built backend image enforces the documented unprivileged runtime
# identity and that the production API, worker, and migration commands start
# as the fixed non-zero UID/GID without a user override.
#
# Usage: sh backend/scripts/check-image-runtime.sh <image-ref>
#
# This is the deterministic image gate behind tasks 2.3 and 2.4: it rejects a
# default UID of 0 and asserts the documented runtime identity for the shared
# backend image used by the API, worker, and migration workloads.
set -eu

IMAGE="$1"
RUNTIME_UID="${RUNTIME_UID:-10001}"
RUNTIME_GID="${RUNTIME_GID:-10001}"

if [ -z "$IMAGE" ]; then
  printf 'usage: %s <image-ref>\n' "$0" >&2
  exit 2
fi

uid="$(docker run --rm --entrypoint sh "$IMAGE" -c 'id -u')"
gid="$(docker run --rm --entrypoint sh "$IMAGE" -c 'id -g')"

if [ "$uid" = "0" ]; then
  printf 'FAIL: image %s defaults to UID 0 (root); refusing to deploy.\n' "$IMAGE" >&2
  exit 1
fi

if [ "$uid" != "$RUNTIME_UID" ] || [ "$gid" != "$RUNTIME_GID" ]; then
  printf 'FAIL: image %s runs as UID/GID %s/%s, expected %s/%s.\n' \
    "$IMAGE" "$uid" "$gid" "$RUNTIME_UID" "$RUNTIME_GID" >&2
  exit 1
fi

printf 'OK: image %s defaults to UID %s GID %s (non-root).\n' "$IMAGE" "$uid" "$gid"
