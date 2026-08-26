## ADDED Requirements

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
