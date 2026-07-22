## Why

Post-response knowledge ingestion currently runs as in-memory work that can be lost when the API process crashes, restarts, or is rescheduled. Confirmed-plant enrichment, profile refresh, and other bounded asynchronous flows need a durable execution foundation before they can be connected safely.

## What Changes

- Add a PostgreSQL-backed application job store with versioned payloads, idempotency keys, ownership, attempts, scheduling, leases, results, errors, and terminal states.
- Add a separately deployed worker that atomically claims eligible jobs, renews leases, retries transient failures with configurable exponential backoff, and recovers work after lease expiry.
- Define the common lifecycle states `pending`, `processing`, `complete`, `partial`, and `failed` and expose authorized status reads for user-visible jobs.
- Require job handlers to validate their payload version and persist domain effects idempotently before completing a job.
- Replace assistant validated-claim ingestion through `asyncio.create_task` with a durable `ingest_validated_claims` job without delaying the user-facing assistant response.
- Add bounded job metrics and structured logs for backlog age, attempts, duration, retries, partial outcomes, failures, and stale-lease recovery without recording sensitive payload content.
- Deploy and operate the worker independently from the API and Alembic migration Job, while reusing existing backend settings, database sessions, provider services, and knowledge ingestion services.
- Keep PostgreSQL as the initial coordination mechanism; do not introduce Redis, Celery, Cloud Tasks, or a general-purpose event bus.

## Capabilities

### New Capabilities

- `durable-background-jobs`: Durable scheduling, atomic claiming, leasing, retries, recovery, idempotency, authorization, and job lifecycle behavior.

### Modified Capabilities

- `knowledge-rag-acquisition`: Persist validated assistant claims through durable background work instead of an in-process task.
- `gcp-deployment-platform`: Deploy, configure, and observe a long-running backend worker separately from the API and migration Job.
- `provider-observability`: Report bounded job backlog, attempt, latency, retry, partial-completion, and failure telemetry without sensitive content.

## Impact

- Adds an Alembic migration, backend job repository and schemas, worker runtime entrypoint, handler registry, and configuration for polling, leases, and retries.
- Adds an authenticated job-status API and corresponding generated OpenAPI TypeScript contracts for user-visible work.
- Changes assistant post-response claim persistence and its tests from in-memory scheduling to durable enqueueing and worker execution.
- Adds worker deployment manifests, local operation documentation, health behavior, and operational metrics.
- Establishes infrastructure later changes can reuse for confirmed-plant enrichment and profile regeneration, but does not implement those workloads in this change.
