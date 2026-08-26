## ADDED Requirements

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
