# Worker Operations

## Running the worker locally

Start the API and worker as separate processes:

```bash
# Terminal 1: API
cd backend && uvicorn app.main:app --reload

# Terminal 2: Worker (enable the worker explicitly)
cd backend && JOBS_WORKER_ENABLED=true python -m app.jobs.worker
```

The application setting defaults the worker to disabled. Set
`JOBS_WORKER_ENABLED=true` in the worker process to begin polling. Set
`JOBS_PRODUCER_ENABLED=true` independently in the API process to enable job
enqueueing; enabling a worker does not enable producers.

Set `JOBS_REQUIRED_CONTRACTS=enrich_confirmed_plant:1` on enrichment-capable
workers. Startup fails before readiness if the closed worker registry does not
contain that exact job type and payload version. Docker Compose sets this check
for the local worker.

Docker Compose starts the separate worker service with consumption enabled and
keeps producers disabled unless explicitly overridden:

```bash
# Observe worker readiness without creating new jobs.
docker compose up backend worker

# Enable both enqueueing and consumption for an end-to-end local run.
JOBS_PRODUCER_ENABLED=true JOBS_WORKER_ENABLED=true \
  docker compose up backend worker
```

## Observing worker behavior

### Logs

The worker emits JSON structured logs with these event names:

| Event | When |
|-------|------|
| `worker_starting` | Worker starts and records its bounded runtime configuration |
| `worker_stopped` | Worker stops with `ctx_outcome` set to `clean` or `timeout` |
| `worker_draining` | Shutdown begins with active count and drain timeout |
| `worker_drain_timeout` | Active handlers exceeded the bounded drain period |
| `worker_cancellation_cleanup_timeout` | A cancellation-resistant handler exceeded the one-second cleanup allowance |
| `worker_signal_handlers_registered` | Signal handlers installed |
| `worker_handler_exception` | Handler raised an unexpected exception |
| `worker_lease_lost` | Lease ownership lost (operation in `ctx_operation`: `renewal`, `complete`, `partial`, `retry`, `fail`) |
| `worker_lease_renewal_error` | Lease renewal failed due to a database transient |
| `worker_dependency_validation_failed` | An enabled worker cannot initialize a registered handler dependency |
| `worker_poll_failed` | Enabled reconciliation or claim polling failed |
| `worker_database_health_check_failed` | Disabled worker database health check failed |
| `worker_disabled_by_configuration` | Consumption is disabled; the process remains alive and checks database connectivity |
| `worker_entrypoint_starting` | Worker entrypoint initializing |
| `job_claimed` | A job attempt was claimed, including attempt, worker identity, and bounded recovery status |
| `job_lease_renewed` / `worker_lease_lost` | Lease renewal succeeded or ownership was lost |
| `job_stale_recovered` | An expired lease was recovered as `lease_expired` or `attempts_exhausted` |
| `job_completed` / `job_partial` | An attempt completed, including duration and bounded outcome metadata |
| `job_retry_scheduled` | A retry was scheduled with category and retry delay |
| `job_failed` | An attempt failed terminally with a sanitized category |

The API emits `job_scheduled` after the request transaction commits. It includes
the job UUID, closed job type, payload version, ownership category, and a
`created` or `reused` scheduling outcome. When available, it also includes the
conversation UUID for request-to-job correlation. Attempt-result events include
the job type, attempt number, duration, outcome, and worker identity. Failure
events add only a closed failure category. Events never include the payload,
idempotency key material, claims, evidence text, prompts, notes, source bodies,
credentials, or tokens.

### Metrics

#### API-owned durable-job metrics

The API process records scheduling outcomes after the assistant-response and
job-enqueue transaction commits. These metrics are exposed through the API
`/metrics` endpoint and scraped by `PodMonitoring/fotosintesis-backend`.

| Metric | Labels | Description |
|--------|--------|-------------|
| `fotosintesis_job_schedules_total` | `job_type`, `outcome` | Committed scheduling outcomes: `created` or `reused` |

#### Worker-owned durable-job metrics

The worker process exposes lifecycle and backlog metrics through its private
metrics listener. Kubernetes scrapes them with
`PodMonitoring/fotosintesis-worker`; no worker Service is created.

| Metric | Labels | Description |
|--------|--------|-------------|
| `fotosintesis_job_claims_total` | (none) | Total job claims by workers |
| `fotosintesis_job_claims_by_type_total` | `job_type` | Total job claims by closed job type |
| `fotosintesis_job_outcomes_total` | `job_type`, `status` | Job outcomes by type and status |
| `fotosintesis_job_attempt_duration_seconds` | `job_type`, `status` | Handler duration by outcome |
| `fotosintesis_job_retries_total` | `job_type`, `category` | Retry events by job type and failure category |
| `fotosintesis_job_stale_recoveries_total` | `job_type`, `outcome` | Stale lease recoveries, including `lease_expired` and `attempts_exhausted` |
| `fotosintesis_job_backlog_count` | `job_type`, `status` | Active backlog only: `pending` and `processing` rows |
| `fotosintesis_job_status_count` | `job_type`, `status` | Durable row count across every lifecycle status |
| `fotosintesis_job_oldest_eligible_age_seconds` | (none) | Age of the oldest eligible pending job |
| `fotosintesis_worker_last_successful_poll_timestamp_seconds` | (none) | Unix timestamp of the last successful reconciliation or disabled-mode database check |
| `fotosintesis_enrichment_acquisition_avoided_total` | (none) | Complete or partial enrichment runs that needed no external acquisition |
| `fotosintesis_enrichment_partial_outcomes_total` | (none) | Durable useful-subset enrichment outcomes |
| `fotosintesis_enrichment_completion_time_seconds` | (none) | Bounded histogram of enqueue-to-terminal time for complete or partial enrichment |

API and worker metric registries are process-local and reset when pods restart.
Scheduling counters must be queried from backend targets. Worker lifecycle and
backlog metrics must be queried from worker targets.

Generic process-local metrics (claims, outcomes, retries, stale recoveries,
backlog snapshots) reset when a worker pod restarts. Durable enrichment
efficacy, in contrast, is reconstructed from PostgreSQL on every worker
restart, so multiple replicas expose identical database-derived totals and
monitoring must aggregate them with `max`, never `sum`.

```promql
sum by (job_type, outcome) (
  rate(fotosintesis_job_schedules_total[5m])
)
```

```promql
max by (job_type, status) (
  fotosintesis_job_backlog_count
)
```

```promql
max by (policy_version, lifecycle_outcome, acquisition_avoided) (
  fotosintesis_enrichment_efficacy_total
)
```

Do not sum identical database snapshot gauges across worker replicas.

**Local development**: When running the worker directly with `python -m app.jobs.worker`,
metrics are available via a local HTTP endpoint on a configurable port. Check the
worker startup logs for the metrics endpoint address.

Labels are restricted to closed values (job type, lifecycle status, failure category).
No job IDs, user IDs, conversation IDs, URLs, scientific names, raw errors, or
payload values are used as labels.

`fotosintesis_job_outcomes_total` uses `lease_lost` when the worker loses lease
ownership during execution and intentionally does not finalize the job.
`cancelled` means a handler was cancelled during worker shutdown; it is likewise
not finalized by that worker and is recoverable after lease expiry. Scheduling
logs may include job and conversation UUIDs for correlation, but metrics never
use either identifier as a label.

The enrichment metrics intentionally have no payload, species, aspect, source,
job, owner, or content labels. Retry and terminal failure monitoring continues
to use `fotosintesis_job_retries_total` and `fotosintesis_job_outcomes_total`
rather than parallel enrichment-specific failure series. Lease loss is a
generic job outcome and is never an enrichment lifecycle outcome: the durable
enrichment lifecycle is closed to `complete`, `partial`, and `failed`, and
`worker_lease_lost` does not produce an enrichment efficacy observation.

## Confirmed-plant enrichment contract

Enrichment policy version `1` identifies a species with the accepted GBIF key
and normalized binomial together when both were taxonomy-validated. If GBIF did
not return an accepted key, the validated normalized binomial is the fallback.
Display names and unvalidated free-form text are never identity material.

Policy v1 carries four explicit aspect sets through execution:

1. `required_aspects` is the complete policy set: general care; light, soil,
   climate and humidity; watering amount and trigger; feeding schedule and
   fertilizer type; pest and disease identification and prevention; and pet,
   human, child and handling safety.
2. `local_covered_aspects` is the subset accepted by all-required local semantic
   judging.
3. `acquisition_aspects` is exactly required minus local coverage and is the
   only set sent to bounded external search.
4. `final_covered_aspects` comes from the normalized local result when nothing
   is missing, or from combined judging of all required aspects when acquisition
   runs. Final missing aspects are required minus final coverage.

The durable outcome mapping is fixed: all required aspects becomes `complete`;
a useful accepted subset becomes `partial`; no accepted support becomes
`failed` with `insufficient_evidence`; transient provider, judge, database or
index failures reuse durable retries and eventually fail; invalid contracts and
invariants fail without retry. Policy v1 permits at most four aspects per search
group, five searches, and three durable attempts.

After the drain timeout, cancellation cleanup receives one additional bounded
second. Python cannot safely force a cancellation-resistant coroutine to stop;
the Kubernetes termination grace period and eventual SIGKILL remain the final
process-level bound. Unfinished jobs retain their leases and recover after expiry.

The Kubernetes worker exposes `/ready` on its private metrics port. An enabled
worker reports ready only after registered handler dependencies validate, a
database reconciliation succeeds, and the durable efficacy telemetry refresh
succeeds. A disabled worker never claims, reconciles, or finalizes jobs and
reports ready only after required handler contracts validate, PostgreSQL
connectivity succeeds, and read-only queue and durable efficacy telemetry
queries succeed. Disabled readiness is read-only pause health, not
active-consumer readiness: a failing telemetry query keeps a disabled worker
unready. Missing migrations or an incompatible `application_jobs` schema
therefore keep a disabled worker unready. Either mode clears readiness after a
poll or health-check failure and retries at the configured poll interval.
Failure to start the private metrics listener is a terminal startup error. GKE
Managed Prometheus scrapes `/metrics` through the worker `PodMonitoring`; no
Service is created.

## Deployment switch policy

A normal deployment requires the worker enabled and ready. The deploy workflow
rejects a producer-enabled/worker-disabled combination because it schedules
jobs nobody consumes. Both switches disabled is allowed only as an explicitly
approved paused deployment (`paused_deployment=true`); that mode is read-only
pause health and is not active consumption. The worker readiness gate verifies
the deployed `JOBS_WORKER_ENABLED=true` plus the required
`enrich_confirmed_plant:1` contract, and skips active-consumer readiness only
for an approved paused deployment.

## Ingestion policy compatibility

Payload version remains `1`. Policy version `1` includes `topic` in the durable
claim identity for existing queued work. Current producers use policy version
`2`, which excludes `topic` from identity so classifier-label drift cannot create
duplicate knowledge. Policy-1 jobs remain supported and retain their original
hashes.

### Backlog diagnosis

```sql
-- Check backlog counts
SELECT status, job_type, count(*) as count
FROM application_jobs
WHERE status IN ('pending', 'processing')
GROUP BY status, job_type;

-- Find oldest eligible pending job
SELECT id, job_type, available_at, attempt_count
FROM application_jobs
WHERE status = 'pending' AND available_at <= NOW()
ORDER BY available_at ASC
LIMIT 1;

-- Find expired processing jobs
SELECT id, job_type, attempt_count, lease_owner, lease_expires_at
FROM application_jobs
WHERE status = 'processing' AND lease_expires_at <= NOW();

-- Inspect a specific job's error
SELECT id, job_type, status, attempt_count, last_error, result
FROM application_jobs
WHERE id = '<job-uuid>';
```

## Retry exhaustion

Unexpected handler exceptions are sanitized as `unexpected_error` and treated as
retryable until `max_attempts` is reached. Raw exception messages are never
persisted, logged, used as metric labels, or exposed through the status API.

A job reaches terminal failure through one of two paths:

1. **Live final handler attempt** — the handler's last attempt runs and
   reaches its retry limit. The `last_error.category` is set to
   `attempts_exhausted` (or the sanitized permanent category) with
   `retryable=false`. The `attempt_count` reflects the actual number of
   handler invocations.

2. **Expired processing lease reconciled after exhaustion** — a crashed
   worker's lease expires and reconciliation finds the attempt count at the
   maximum. The `last_error.category` is set to `attempts_exhausted` with
   `retryable=false`. The `attempt_count` equals `max_attempts`.

### Enrichment durable progress and terminal meaning

Confirmed-plant enrichment finalizes exhausted jobs from the durable progress
checkpoint (`enrichment_job_progress`), never from a handler's zero snapshot.
Useful accepted coverage is the union of semantically accepted local aspects
and durably persisted accepted aspects. Final semantic judge output that has
not passed source binding and persistence is diagnostic only: **judge-only
coverage is not durable progress** and can never turn an exhausted job into
`partial`.

The three terminal meanings after exhaustion are:

- **`complete`** — every required aspect has accepted coverage.
- **`partial`** — at least one required aspect has useful accepted evidence
  checkpointed (persisted and/or locally covered), but the workflow did not
  fully converge; this means accepted progress survived. The bounded result
  carries the applicable operational limitation (`retry_exhausted`,
  `workflow_incomplete`, or `indexing_deferred`) chosen from the actual
  unfinished stage: persisted-but-not-indexed evidence is `indexing_deferred`,
  an exhausted final attempt is `retry_exhausted`, and an interrupted attempt
  is `workflow_incomplete`.
- **`failed` + `attempts_exhausted`** — no useful accepted coverage survived in
  the checkpoint, so the job reports total failure.

Live finalization and crash reconciliation (`reconcile_expired_processing`)
apply the same partial-versus-failed decision rule and write the matching
immutable terminal observation in the same transaction as the terminal
transition. Terminal efficacy values are derived from the durable checkpoint
and use enqueue-to-terminal duration consistently across complete, semantic
partial, failure-derived partial, and failed outcomes.

**Do not reset terminal enrichment jobs in place.** Terminal telemetry
(`enrichment_telemetry_observations`) is immutable, and in-place resets break
the "exactly one observation per terminal job" invariant and discard audit
history. For an approved rerun:

1. Create a new logical job/run with a fresh `run_id`, idempotency key, and
   active-deduplication key.
2. Preserve the existing evidence and telemetry history unchanged; the new run
   converges idempotently on the same stable content identities.

To diagnose an exhausted enrichment job:

1. Query the job to inspect `last_error` and `result`
2. If the issue is transient and an approved rerun is warranted, enqueue a new
   logical run rather than rewriting the terminal job. Do not reuse the
   in-place reset SQL below for enrichment jobs.

For non-enrichment jobs that produced no correct domain effects, an in-place
reset remains available:

```sql
UPDATE application_jobs
SET status = 'pending',
    attempt_count = 0,
    lease_owner = NULL,
    lease_token = NULL,
    lease_expires_at = NULL,
    last_error = NULL,
    completed_at = NULL,
    available_at = NOW()
WHERE id = '<job-uuid>';
```

   This clears all lease fields, resets the attempt count, and makes the job
   eligible for the next poll cycle. Do not use this SQL for jobs that
   produced correct domain effects; create a new idempotency key for genuinely
   new logical runs.

## Payload version compatibility

When rolling out new handler versions:

- Keep old payload version handlers registered until all in-flight jobs complete
- New handlers should declare `supported_payload_versions()` including all versions still in flight
- Jobs with unsupported payload versions fail immediately with `unsupported_payload_version`
- Supported versions are retained across forward-compatible schema changes.
  A forward fix must not require re-executing completed jobs with the same
  idempotency key; use a new key for genuinely new work.

## Forward-fix recovery

If a handler produces incorrect domain effects:

1. Disable enqueuing (`JOBS_PRODUCER_ENABLED=false`) and optionally scale
   the worker Deployment to 0
2. Apply a data fix directly to the database
3. For jobs that need re-execution with corrected logic, create a new job with
   a different idempotency key
4. Or reset the failed/succeeded jobs:
   ```sql
   UPDATE application_jobs
   SET status = 'pending',
       attempt_count = 0,
       lease_owner = NULL,
       lease_token = NULL,
       lease_expires_at = NULL,
       last_error = NULL,
       result = NULL,
       completed_at = NULL,
       available_at = NOW()
   WHERE status IN ('failed', 'complete')
   AND job_type = '<job-type>';
   ```

   **Warning**: This re-runs domain effects. Only use when you have verified
   idempotency or applied compensating data fixes first.

Confirmed-plant confirmation has mandatory scheduling semantics. Never work
around an unavailable queue by committing confirmation without its enrichment
job and candidate-policy association. For forward recovery, preserve additive
jobs, associations, evidence, validation records and taxonomy provenance; ship
a compatible worker or forward-fix migration, then allow pending work to resume.

## Rollback procedure

To roll back to a previous release:

1. Identify the last healthy backend and worker image tags from the
   `fotosintesis-release-state` ConfigMap (`backend-image-tag`).
2. Deploy the previous backend and worker images together, ensuring both
   use the same SHA-based tag.
3. Confirm the existing database schema remains compatible with the target API
   and worker. Migrations are forward-only: restore an approved backup or ship a
   reviewed forward-fix migration when it is not compatible.
4. Disable `JOBS_PRODUCER_ENABLED` on the new backend if the rollback
   target does not support durable jobs.
5. Verify the worker Deployment rolls out before reporting success.

For enrichment releases, deploy and verify a worker requiring
`enrich_confirmed_plant:1` before enabling a backend that schedules confirmation
work. During rollback, keep a compatible enqueueing backend and worker deployed.
If the rollback target cannot enqueue and retain that contract, make confirmation
temporarily unavailable by disabling producers; do not silently confirm without
scheduling. Worker consumption may be paused while compatible jobs remain
durable for forward recovery.

Both the API and worker must use the same backend image SHA during rollback.
Keep handlers for every persisted payload version still in flight. Deploying
only one process, or removing a handler required by persisted jobs, creates an
incompatible runtime.
