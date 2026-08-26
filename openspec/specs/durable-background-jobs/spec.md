## Purpose

Define durable PostgreSQL-backed background job scheduling, execution, recovery, retry, lifecycle, authorization, and worker operation requirements.

## Requirements

### Requirement: Durable job scheduling

The system SHALL persist bounded asynchronous application work in PostgreSQL before acknowledging that the work has been scheduled. Every job SHALL include a closed job type, payload version, idempotency key, lifecycle status, attempt policy, eligibility time, and lifecycle timestamps.

#### Scenario: Job scheduling succeeds
- **WHEN** an application flow schedules valid background work within a successful transaction
- **THEN** the system commits a job with status `pending` before reporting that the work was scheduled
- **AND** the job remains available after the API process terminates

#### Scenario: Scheduling transaction rolls back
- **WHEN** the transaction containing a new job is rolled back
- **THEN** the system does not expose or execute that uncommitted job

### Requirement: Atomic job claiming and leasing

The worker SHALL claim eligible work through an atomic PostgreSQL operation and MUST NOT allow more than one active, non-expired lease for the same job.

#### Scenario: Concurrent workers claim work
- **WHEN** two workers concurrently attempt to claim the same eligible job
- **THEN** only one worker transitions that job to `processing` with its lease identity
- **AND** the other worker continues without executing that lease

#### Scenario: Worker renews a lease
- **WHEN** a handler remains active near its lease expiry
- **THEN** the owning worker can extend the lease using a conditional update tied to its lease identity

#### Scenario: Worker loses lease ownership
- **WHEN** a worker attempts to finalize a job after its lease is no longer current
- **THEN** the system rejects that stale finalization
- **AND** the worker does not overwrite the state owned by another lease

### Requirement: Expired lease recovery

The system SHALL make an unfinished `processing` job eligible for recovery after its lease expires, subject to its attempt policy.

#### Scenario: Worker crashes during execution
- **WHEN** a worker terminates without completing a leased job and the lease expires
- **THEN** another worker can claim the job for a later attempt

#### Scenario: Expired job has exhausted attempts
- **WHEN** a processing lease expires after the job has reached its maximum attempt count
- **THEN** the system transitions or reconciles the job to `failed` instead of executing another attempt

### Requirement: Retry and terminal failure policy

The worker SHALL retry only failures classified as retryable and SHALL schedule retries using configurable exponential backoff bounded by a configured cap and maximum attempt count.

#### Scenario: Retryable handler failure
- **WHEN** a handler reports a retryable failure before exhausting attempts
- **THEN** the worker returns the job to `pending`
- **AND** sets its next eligibility time according to the configured backoff policy

#### Scenario: Non-retryable handler failure
- **WHEN** a handler reports an invalid payload, unsupported payload version, or another non-retryable failure
- **THEN** the worker marks the job `failed` without scheduling another execution

#### Scenario: Retry limit exhausted
- **WHEN** the final permitted attempt fails
- **THEN** the worker marks the job `failed` and retains bounded final failure metadata

### Requirement: Versioned and idempotent job handlers

Every job handler MUST validate its declared payload version and SHALL persist domain effects idempotently for the job's stable idempotency key.

#### Scenario: Equivalent job is scheduled again
- **WHEN** a producer schedules the same job type and idempotency key more than once
- **THEN** the system returns or reuses the existing job
- **AND** does not create another logical unit of work

#### Scenario: Job repeats after domain commit
- **WHEN** a handler commits some or all domain effects but the job is retried before completion is recorded
- **THEN** the repeated handler execution does not create duplicate domain effects

#### Scenario: Unsupported payload version is claimed
- **WHEN** no registered handler supports the persisted payload version
- **THEN** the worker records a bounded non-retryable failure without interpreting the payload dynamically

### Requirement: Job lifecycle results

The worker SHALL represent successful work as `complete`, useful incomplete work as `partial`, and exhausted or permanent failure as `failed` with bounded result metadata.

#### Scenario: Handler completes all work
- **WHEN** a handler successfully persists all intended domain effects
- **THEN** the worker marks the job `complete` and records its completion timestamp

#### Scenario: Handler produces a useful partial result
- **WHEN** a handler persists a useful subset of its intended domain effects and reports explicit remaining limitations
- **THEN** the worker marks the job `partial` with bounded result and limitation metadata

#### Scenario: Handler cannot produce a useful result
- **WHEN** a handler reaches a permanent failure or exhausts retries without useful domain effects
- **THEN** the worker marks the job `failed`

### Requirement: Authorized job status

The backend SHALL allow authenticated users to read metadata-only status for jobs associated with their own user identity and MUST NOT expose raw job payloads or another user's job existence.

#### Scenario: Owner reads job status
- **WHEN** an authenticated user requests a job associated with that user
- **THEN** the response includes job type, lifecycle status, attempts, timestamps, and bounded result or error metadata
- **AND** excludes raw payloads, claims, prompts, user notes, source bodies, and tokens

#### Scenario: Another user requests job status
- **WHEN** an authenticated user requests a job associated with another user
- **THEN** the backend returns the same not-found behavior used for an unknown job

#### Scenario: User requests an internal job
- **WHEN** an authenticated user requests a system-owned job with no user association
- **THEN** the backend does not expose that job through the user status endpoint

### Requirement: Worker lifecycle

The worker SHALL poll for bounded batches of eligible jobs, support configurable concurrency, and stop gracefully without losing committed work.

#### Scenario: No work is eligible
- **WHEN** a worker poll finds no eligible jobs
- **THEN** the worker waits for the configured idle interval before polling again

#### Scenario: Worker receives shutdown signal
- **WHEN** the worker receives a termination signal
- **THEN** it stops claiming new jobs and allows active handlers a bounded drain period
- **AND** unfinished jobs remain recoverable after their leases expire

### Requirement: Dependency-safe worker readiness startup

The worker SHALL start its private readiness and metrics listener before validating or constructing potentially expensive production handler dependencies. Readiness MUST remain false until the configured handler registry validates and durable reconciliation succeeds. Supplying an explicit handler registry MUST NOT construct or register unrelated global production handlers.

#### Scenario: Configured dependency is invalid
- **WHEN** worker startup encounters an invalid or missing provider dependency
- **THEN** the readiness listener responds with unavailable status without waiting for successful dependency construction
- **AND** the worker claims no jobs
- **AND** logs and metrics contain only bounded failure categories

#### Scenario: Explicit registry is supplied
- **WHEN** a caller constructs a worker with an explicit compatible handler registry
- **THEN** startup validates and uses that registry
- **AND** does not construct unrelated global handlers or provider clients

#### Scenario: Dependencies and reconciliation recover
- **WHEN** previously invalid dependencies become valid and durable reconciliation succeeds
- **THEN** readiness transitions to available
- **AND** eligible work can be claimed according to normal worker policy

#### Scenario: Disabled readiness is read-only pause health
- **WHEN** the worker is disabled by configuration
- **THEN** it validates required handler contracts, checks PostgreSQL connectivity, and queries queue and durable efficacy telemetry
- **AND** it does not validate external providers, reconcile, claim, renew, or finalize jobs
- **AND** its `/ready` reports pause health only after those read-only queries succeed, and remains unavailable while a telemetry query fails

### Requirement: Durable terminal efficacy observations

Every terminal enrichment job SHALL produce exactly one immutable durable observation, inserted atomically in the same transaction as the terminal job transition. Retries and non-enrichment jobs SHALL produce none. Unknown or malformed policy versions SHALL use the closed `"unsupported"` label. Successful finalization SHALL never emit a lease-loss outcome.

#### Scenario: Complete, partial, and failed terminal outcomes each produce one observation
- **WHEN** an enrichment job commits a `complete`, `partial`, or `failed` terminal transition
- **THEN** exactly one immutable observation row is inserted in the same transaction with a matching lifecycle outcome
- **AND** the observation is immutable in PostgreSQL

#### Scenario: Retries produce no terminal observation
- **WHEN** an enrichment job is scheduled for retry
- **THEN** no terminal efficacy observation is created

#### Scenario: Malformed exhausted policy uses the unsupported label
- **WHEN** an exhausted enrichment job has a missing, string, boolean, zero, negative, or unknown positive policy version
- **THEN** reconciliation emits exactly one failed observation with the `"unsupported"` label

#### Scenario: Successful finalization never emits lease loss
- **WHEN** renewal and finalization race and finalization commits the terminal transition first
- **THEN** the later renewal observes the committed terminal state
- **AND** no `worker_lease_lost` log or generic `lease_lost` metric is emitted

### Requirement: Durable lease-loss verification

Lease-loss handling SHALL cancel or disregard stale execution and MUST NOT finalize a job using a lost lease. The outcome SHALL be verifiable through durable job state and bounded structured events or metrics without requiring transient private in-memory execution state to remain observable after cleanup.

#### Scenario: Lease ownership is replaced during execution
- **WHEN** a running worker loses lease ownership to another lease identity
- **THEN** it does not complete, partially complete, retry, or fail the job using the stale lease
- **AND** emits one bounded lease-loss outcome for that execution
- **AND** preserves the replacement lease's durable state

#### Scenario: Lease-loss execution state is cleaned up
- **WHEN** stale execution is cancelled after lease loss
- **THEN** the worker may remove its private execution state promptly
- **AND** durable state plus bounded events remain sufficient to verify correct behavior

### Requirement: Failure-derived enrichment partial

The worker SHALL derive terminal status for a failed or exhausted enrichment attempt from its locked durable progress checkpoint. Useful accepted coverage SHALL produce `partial` with a bounded result and closed non-retryable terminal error; no useful accepted coverage SHALL produce `failed`.

#### Scenario: Live final attempt has useful accepted progress

- **WHEN** the final permitted attempt fails after accepted local or persisted coverage was checkpointed
- **THEN** the worker commits `partial`, its bounded result, terminal error, and matching efficacy observation atomically

#### Scenario: Reconciliation finds useful accepted progress

- **WHEN** an expired final lease is reconciled after accepted progress was checkpointed
- **THEN** reconciliation uses the same partial-versus-failed rule as live finalization

#### Scenario: Exhausted job has no accepted progress

- **WHEN** a live or reconciled exhausted enrichment job has no accepted local or persisted coverage
- **THEN** it becomes `failed` with `attempts_exhausted`

### Requirement: Deterministic terminal enrichment metadata

Complete and normal partial transitions SHALL clear stale retry errors. Every new terminal enrichment transition SHALL retain exactly one matching immutable efficacy observation, and retries SHALL retain none.

#### Scenario: Retry later completes

- **WHEN** an enrichment job has a stale retry error and a later attempt completes or returns a normal semantic partial
- **THEN** the terminal transition clears the stale retry error

#### Scenario: Terminal transition commits

- **WHEN** an enrichment job commits complete, partial, or failed
- **THEN** exactly one matching terminal efficacy observation commits in the same transaction
