## Context

`AssistantService.chat` currently returns the persisted assistant response and then calls `_schedule_validated_claim_ingestion`, which starts `_ingest_validated_claims_background` through `asyncio.create_task`. That coroutine opens a new `AsyncSessionLocal`, invokes the existing `AssistantTools.ingest_validated_claims` path, and commits or rolls back independently. The work is best effort: process termination loses tasks that have not completed, there is no retry schedule, and operators cannot inspect a durable outcome.

The backend already uses async SQLAlchemy sessions, PostgreSQL in deployed environments, Alembic migrations, typed settings, structured logs, and a backend container image. Kubernetes currently deploys the API and a one-shot migration Job, but no long-running application worker. The first durable handler will ingest claims that the assistant's existing semantic judge has already validated. Confirmed-plant enrichment and profile refresh will be separate changes built on this foundation.

## Goals / Non-Goals

**Goals:**

- Persist bounded asynchronous work before reporting that it has been scheduled.
- Allow multiple workers to claim work safely, recover expired leases, and retry transient failures.
- Define versioned job payload and result contracts with durable, authorized status visibility.
- Make handler retries converge on one domain result through explicit idempotency.
- Move validated assistant-claim ingestion out of API-process memory without delaying chat responses.
- Deploy and observe a worker independently while reusing the backend image and services.

**Non-Goals:**

- No Redis, Celery, Cloud Tasks, Kafka, or general-purpose event bus.
- No cron scheduler, notification delivery, plant enrichment, or profile regeneration.
- No exactly-once guarantee for arbitrary external side effects.
- No semantic reclassification of validated claims inside the worker.
- No hardcoded keyword matching, token-presence checks, regex semantic routing, or language-specific word lists; botanical semantics remain owned by the multilingual classifier, schema-validated model outputs, and semantic judges.

## Decisions

### Decision 1: Use PostgreSQL as the initial job store and coordinator

Add an `application_jobs` table containing UUID identity, optional `user_id`, job type, payload version, JSON payload, status, unique idempotency key, attempt count, maximum attempts, `available_at`, lease owner and expiry, sanitized last-error metadata, JSON result, and lifecycle timestamps. PostgreSQL is already required, transactional enqueueing is valuable, and expected volume is bounded.

Alternative considered: introduce a broker. Rejected because it adds infrastructure and failure modes before workload volume demonstrates a need. The handler boundary will remain independent enough to migrate later.

### Decision 2: Claim with short transactions and expiring leases

A worker selects an eligible `pending` job or a recoverable expired `processing` job using `FOR UPDATE SKIP LOCKED`, updates the lease and attempt metadata, and commits before executing the handler. Handler network and embedding operations occur outside the claim transaction. Completion, partial completion, retry scheduling, and terminal failure use a conditional update requiring the same lease owner.

The worker renews leases during long handlers. If renewal or finalization discovers that ownership was lost, it stops claiming success and relies on handler idempotency. Graceful shutdown stops polling, allows a bounded drain interval, and then leaves unfinished leases to expire.

Alternative considered: hold a database lock for the complete handler execution. Rejected because provider calls could create long transactions and block other workers.

### Decision 3: Use at-least-once execution with domain idempotency

The job table has a unique `(job_type, idempotency_key)` constraint. Enqueueing the same logical work returns the existing job rather than adding another row. A deliberate new run changes the key by including the relevant policy or payload version.

Job-level deduplication does not cover a crash after domain commit but before job completion. The first handler therefore computes a stable ingestion key for every validated claim from normalized confirmed taxonomy, source URL, covered aspects, claim, evidence quote, and ingestion-policy version. Persisted validated-claim documents store that nullable unique key, so retries skip already committed claims while legacy documents remain valid.

Alternative considered: claim that leases provide exactly-once execution. Rejected because process failure can always occur between a domain commit and a job-state update.

### Decision 4: Make handlers typed and versioned

A registry maps a closed job-type identifier to a handler and supported payload versions. Each handler validates JSON through a Pydantic schema before performing work and returns a typed complete or partial result. Unsupported versions and permanently invalid payloads fail without repeated execution; transient typed failures are eligible for retry.

The common runtime owns polling, claims, lease renewal, retry calculation, and state transitions. Handlers own domain transactions and idempotency. The database enforces a closed set of job types. Unknown job types cannot be persisted through the current schema. Unsupported payload versions and malformed payloads fail safely without dynamic interpretation. New job types require a migration, schema update, handler registration, and compatibility contract.

### Decision 5: Classify retries explicitly

Handlers return or raise sanitized typed failure metadata containing category and retryable status. Retryable failures schedule `available_at` using configurable exponential backoff capped by configuration. Non-retryable payload, schema, or invariant failures become terminal immediately. Reaching the configured attempt limit also becomes terminal.

The first implementation does not infer retryability by parsing exception or user-facing message text. Unexpected exceptions are sanitized, logged, rolled back, and treated according to one conservative documented category.

### Decision 6: Enqueue validated claims after successful assistant persistence

The assistant constructs a versioned `ingest_validated_claims` payload only when normalized ingestion claims are non-empty. The job is inserted through the same request-owned session used for conversation persistence so the response record and enqueue commit together at the API transaction boundary. The API does not wait for worker execution.

The worker opens its own session, invokes the existing claim ingestion services, commits idempotent claim effects, and records a bounded result containing counts and failure categories rather than source text. The job payload is not returned by the status API or copied into logs.

Alternative considered: publish after the request transaction commits. Rejected because a process crash between commit and publish would recreate the loss window.

### Decision 7: Expose metadata-only status with ownership enforcement

`GET /jobs/{job_id}` returns lifecycle state, type, attempt summary, timestamps, and bounded result/error metadata for authenticated user-owned jobs. It does not return the raw payload, claims, prompts, notes, source bodies, or tokens. A missing job and a job owned by another user produce the same not-found behavior. Internal system jobs without a user owner are not exposed through this endpoint.

### Decision 8: Deploy the worker from the immutable backend image

Add a worker entrypoint such as `python -m app.jobs.worker` and a separate Kubernetes Deployment using the same backend commit-SHA image, runtime service account, secrets, provider configuration, and Cloud SQL connectivity. It has no Service. A private readiness endpoint on the metrics listener becomes healthy after database reconciliation, while worker heartbeat/backlog metrics provide runtime visibility; deployment workflows verify worker rollout alongside the backend.

Local development can run the same module as a separate process. The migration Job remains one-shot and is not reused as a worker.

## Risks / Trade-offs

- **Duplicate execution after lease loss** -> Require stable job and claim ingestion keys, unique constraints, and idempotent domain transactions.
- **Worker crashes during provider calls** -> Use expiring leases and bounded renewal; retries recover the job without holding database locks.
- **Poison jobs consume capacity** -> Distinguish retryable failures, cap attempts and backoff, and retain terminal diagnostics.
- **Database polling adds load** -> Index status and `available_at`, claim bounded batches, and configure idle polling intervals.
- **Payloads contain validated claims** -> Restrict database access, never expose payloads through user APIs, and exclude payload content from logs and metrics.
- **Schema evolution strands old jobs** -> Version payloads explicitly and retain handlers for supported in-flight versions during rollout.
- **Worker outage grows backlog** -> Expose queue depth, oldest eligible age, attempt outcomes, and worker deployment health.
- **In-memory metrics reset with processes** -> Preserve the repository's current metrics model for this slice while ensuring labels remain bounded; durable job rows remain the source for operational reconciliation.

## Migration Plan

1. Add `application_jobs`, indexes, constraints, and nullable validated-claim ingestion keys without enabling producers.
2. Deploy the worker with the handler registry and polling disabled or with no eligible job types; verify database connectivity and clean shutdown.
3. Enable the `ingest_validated_claims` handler and enqueue path behind configuration only after migration, worker, retry, idempotency, and observability gates pass. The former in-memory task path is not restored.
4. Verify enqueue, execution, retries, deduplication, metrics, authorized status reads, and worker rollout in development.
5. Add future job types only through their own specs, payload versions, handlers, and idempotency contracts.

Rollback disables new enqueueing and worker consumption while preserving job rows for diagnosis. Database columns and tables remain additive. After durable jobs have executed, operators either re-enable a compatible worker or apply a forward fix; rollback never reintroduces in-memory ingestion.

## Open Questions

No blocking product questions remain. Poll interval, lease duration, maximum attempts, backoff base/cap, worker concurrency, and drain timeout will use conservative documented defaults and remain environment-configurable.
