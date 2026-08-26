## ADDED Requirements

### Requirement: Durable job observability

The system SHALL emit structured logs and bounded metrics for durable job scheduling, claiming, attempts, retries, lease recovery, duration, partial completion, terminal failure, backlog size, and oldest eligible job age without exposing sensitive job content.

#### Scenario: Job is scheduled
- **WHEN** a producer commits a durable job
- **THEN** the system records job type, payload version, correlation identifiers when available, ownership category, and scheduling outcome
- **AND** does not log the raw payload or idempotency key material

#### Scenario: Worker attempt completes
- **WHEN** a worker attempt completes, returns a partial result, schedules a retry, or fails permanently
- **THEN** the system records job type, attempt number, duration, outcome, sanitized failure category when applicable, and worker identity
- **AND** excludes claims, prompts, source bodies, evidence quotes, user notes, tokens, and credentials

#### Scenario: Expired lease is recovered
- **WHEN** a worker claims a job whose previous processing lease expired
- **THEN** the system increments a stale-lease recovery metric and emits a bounded structured event

#### Scenario: Job backlog is observed
- **WHEN** runtime metrics are collected
- **THEN** the metrics include bounded job counts by lifecycle status and job type
- **AND** include the age of the oldest eligible pending job without using user identifiers as metric labels

### Requirement: Bounded job telemetry labels

Durable job metrics MUST use bounded labels and MUST NOT label time series by job identifier, user identifier, conversation identifier, URL, scientific name, error message, or other unbounded payload data.

#### Scenario: Job metric is emitted
- **WHEN** the system increments a job counter or observes job duration
- **THEN** labels are limited to closed values such as job type, lifecycle outcome, and sanitized failure category

#### Scenario: Operator correlates a job failure
- **WHEN** an operator investigates a specific job through structured logs
- **THEN** logs may include the job UUID and bounded correlation identifiers
- **AND** metrics remain free of those high-cardinality identifiers
