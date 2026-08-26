## ADDED Requirements

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
