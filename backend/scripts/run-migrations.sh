#!/usr/bin/env sh
# Production migration entrypoint shared by the Kubernetes migration Job and
# the image smoke tests.
#
# The migration Job and the smoke tests must invoke this exact script so a
# single committed definition drives both paths. It:
#   1. Requires the fixed backend runtime identity (UID/GID 10001:10001) so a
#      root override is rejected before touching the database.
#   2. Bounded-waits for the Cloud SQL proxy (or a local PostgreSQL) at
#      PROXY_HOST:PROXY_PORT (default 127.0.0.1:5432).
#   3. Runs `alembic upgrade head`.
#
# Usage: sh /app/scripts/run-migrations.sh [proxy-port]
set -eu

PROXY_HOST="${MIGRATION_PROXY_HOST:-127.0.0.1}"
PROXY_PORT="${1:-${MIGRATION_PROXY_PORT:-5432}}"
WAIT_SECONDS="${MIGRATION_WAIT_SECONDS:-60}"

uid="$(id -u)"
gid="$(id -g)"
if [ "$uid" != "10001" ] || [ "$gid" != "10001" ]; then
  printf 'FATAL: migrations must run as UID/GID 10001:10001, got %s:%s\n' \
    "$uid" "$gid" >&2
  exit 1
fi

python - "$PROXY_HOST" "$PROXY_PORT" "$WAIT_SECONDS" <<'PY'
import socket
import sys
import time

host, port, deadline = sys.argv[1], int(sys.argv[2]), time.monotonic() + float(sys.argv[3])
while True:
    try:
        with socket.create_connection((host, port), timeout=1):
            break
    except OSError:
        if time.monotonic() >= deadline:
            raise SystemExit(
                f"Proxy/PostgreSQL at {host}:{port} did not become ready "
                f"within {float(sys.argv[3])} seconds"
            )
        time.sleep(1)
PY

exec alembic upgrade head
