#!/bin/sh
# Run backend tests inside the photosynthesis-backend container against the
# dockerized PostgreSQL. Usage: ./backend/tests/run-in-container.sh [pytest args...]
#
# The clean per-test integration schemas are created with metadata.create_all,
# which skips tables that already exist in the default "public" schema. The
# test database must therefore be a separate, unmigrated database whose public
# schema has no application tables.
exec docker exec -w /workspace/backend \
  -e TEST_DATABASE_URL="postgresql+asyncpg://fotosintesis:fotosintesis@photosynthesis-postgres-1:5432/fotosintesis_test" \
  -e JOBS_PRODUCER_ENABLED=false \
  photosynthesis-backend-1 sh -c "python3 -m pytest \"\$@\"" sh "$@"
