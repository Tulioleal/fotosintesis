## ADDED Requirements

### Requirement: Durable validated assistant claim ingestion

The system SHALL persist normalized source-supported assistant claims through a durable `ingest_validated_claims` job instead of in-process background tasks. Enqueueing SHALL NOT delay execution of the ingestion handler before returning the assistant response, and the handler MUST preserve the existing trusted-source, final-judge support, rollback, chunking, embedding, and indexing rules.

#### Scenario: Assistant emits validated ingestion claims
- **WHEN** the assistant persists a response with one or more normalized ingestion claims supported by the final semantic judge
- **THEN** the same request transaction persists a versioned `ingest_validated_claims` job associated with the user and conversation
- **AND** the assistant response can return without waiting for claim ingestion, embedding, or indexing to execute

#### Scenario: Assistant emits no validated claims
- **WHEN** the final assistant state contains no normalized source-supported ingestion claims
- **THEN** the system does not create an `ingest_validated_claims` job

#### Scenario: Assistant persistence rolls back
- **WHEN** persistence of the assistant response and its enqueue operation rolls back
- **THEN** no ingestion job from that failed response becomes eligible for execution

### Requirement: Idempotent validated claim persistence

The durable validated-claim handler SHALL use a stable ingestion identity derived from normalized confirmed taxonomy, source provenance, covered aspects, supported claim, evidence quote, and ingestion policy version so repeated attempts do not duplicate equivalent knowledge documents, chunks, or embeddings.

#### Scenario: Handler retries after claim persistence
- **WHEN** a validated claim was committed before a worker lost its lease or failed to record job completion
- **THEN** the next attempt recognizes the persisted ingestion identity
- **AND** does not create duplicate knowledge documents, chunks, or embeddings for that claim

#### Scenario: Job contains multiple claim outcomes
- **WHEN** some claims are persisted successfully and other eligible claims cannot be persisted after their allowed handling
- **THEN** the handler records bounded successful, skipped, and failed counts
- **AND** can return a `partial` result without placing raw claims or evidence text in job result metadata

#### Scenario: Permanently invalid claim payload
- **WHEN** a persisted job payload does not satisfy the versioned validated-claim schema
- **THEN** the handler performs no knowledge persistence for that invalid payload
- **AND** reports a non-retryable sanitized failure

### Requirement: Durable claim ingestion degradation

Failure or delay of durable validated-claim ingestion MUST NOT retract or block the already persisted user-facing assistant response.

#### Scenario: Worker is unavailable after chat response
- **WHEN** an assistant response and ingestion job are committed but no worker is available
- **THEN** the response remains available to the user
- **AND** the pending job remains eligible when a worker becomes available

#### Scenario: Ingestion exhausts retries
- **WHEN** durable claim ingestion reaches its maximum attempts without a useful persisted result
- **THEN** the job remains inspectable as `failed` with bounded failure metadata
- **AND** the assistant response remains available
