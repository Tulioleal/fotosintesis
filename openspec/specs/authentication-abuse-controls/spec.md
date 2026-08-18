## Purpose

Define distributed, privacy-preserving abuse controls for authentication operations.

## Requirements

### Requirement: Distributed authentication limit policy

The system SHALL enforce documented, configurable authentication abuse limits through shared state across all application replicas for registration, credential verification, recovery initiation, recovery confirmation, and relevant Auth.js POST operations.

#### Scenario: Limit is reached across replicas

- **WHEN** requests in one configured limit window are handled by different application replicas and collectively exhaust a limit
- **THEN** every replica rejects further matching requests until the shared limit permits another attempt

#### Scenario: Unrelated authenticated traffic continues

- **WHEN** an authentication operation exhausts one of its limits
- **THEN** requests outside the matching authentication limit keys continue under their own authorization and abuse controls

### Requirement: Source-aware and account-aware limit keys

The system SHALL apply source-derived limits to every covered operation and SHALL additionally apply normalized account-derived limits to credential verification, recovery initiation, and other account-sensitive operations. Account-derived keys MUST use a keyed one-way digest and MUST NOT persist or expose raw email addresses or account identifiers.

#### Scenario: Credential attempts rotate source addresses

- **WHEN** attempts for the same normalized account arrive from different trusted source identities
- **THEN** the shared account-aware limit bounds those attempts independently of the source-aware limits

#### Scenario: One source targets multiple accounts

- **WHEN** one trusted source identity attempts authentication operations for multiple accounts
- **THEN** the source-aware limit bounds the aggregate attempts from that source

#### Scenario: Limiter state is inspected

- **WHEN** persisted limiter keys or diagnostics are inspected
- **THEN** they contain neither raw account identifiers nor raw source addresses

### Requirement: Enumeration-resistant rejection contract

The system SHALL return a bounded retry contract for rejected requests without exposing sensitive limiter keys or account state. Recovery initiation and confirmation MUST preserve the same observable response body and equivalent limiter behavior for known and unknown accounts.

#### Scenario: Non-recovery request is limited

- **WHEN** a covered non-recovery operation is rejected by the limiter
- **THEN** the response uses `429 Too Many Requests`
- **AND** includes a bounded `Retry-After` value derived from the active limit window
- **AND** does not identify the exhausted key or disclose account existence

#### Scenario: Recovery initiation is below the limit

- **WHEN** syntactically valid recovery requests target an existing account and a missing account below the applicable limits
- **THEN** both requests receive the same neutral response body and status contract

#### Scenario: Recovery request is limited

- **WHEN** recovery initiation or confirmation is rejected for either a known or unknown account
- **THEN** the response preserves the endpoint's neutral body contract
- **AND** any status and retry metadata are equivalent for the same active limit state

#### Scenario: Schema-invalid recovery confirmation payload

- **WHEN** a recovery-confirmation payload is rejected by request-body validation (for example a token below the configured minimum length)
- **THEN** the response is a deterministic generic `422` validation error
- **AND** the response does not reveal any token-state, account, or storage detail

#### Scenario: Token-shaped recovery confirmation guesses stay neutral

- **WHEN** well-shaped recovery-confirmation tokens reach token-state handling
- **THEN** the response and limiter behavior are neutral regarding token existence, expiration, or use
- **AND** rotating the source address cannot bypass the token-derived account bound

The application limiter protects schema-valid guesses; volumetric malformed traffic remains an ingress/edge concern and is not an application-limiter claim.

### Requirement: Bounded limiter storage failure behavior

The system SHALL define an explicit storage-failure policy for every covered endpoint. Credential verification and recovery confirmation MUST fail closed or use a strictly bounded local fallback, and registration and recovery initiation MUST NOT become unbounded password-hashing, row-creation, or delivery paths.

#### Scenario: Shared storage fails during credential verification

- **WHEN** the limiter cannot atomically evaluate credential verification limits
- **THEN** authentication is denied or admitted only through the documented strictly bounded fallback
- **AND** the response does not expose account state or storage details

#### Scenario: Shared storage fails during recovery initiation

- **WHEN** the limiter cannot atomically evaluate a recovery initiation request
- **THEN** the request does not create an unbounded recovery token or delivery action
- **AND** the user-facing response remains neutral

### Requirement: Successful authentication does not bypass active limits

The system SHALL reset or relax only the documented account-specific credential counter after successful authentication and MUST retain source-wide and other independently active protections.

#### Scenario: Valid credentials follow failed attempts

- **WHEN** a user authenticates successfully before a source-wide limit expires
- **THEN** the documented account-specific failure state may be relaxed
- **AND** the source-wide limit remains active and cannot be cleared by the successful request

### Requirement: Privacy-preserving limiter observability and lifecycle

The system SHALL emit bounded metrics for allowed, rejected, and storage-failure outcomes by closed endpoint category and SHALL expire or clean limiter state according to documented retention rules. Metrics and logs MUST NOT contain passwords, tokens, raw emails, raw account identifiers, raw source addresses, or digest keys.

#### Scenario: Limiter outcome is recorded

- **WHEN** a covered request is allowed, rejected, or encounters limiter storage failure
- **THEN** one metric is recorded with only the configured endpoint category and outcome labels

#### Scenario: Limiter state expires

- **WHEN** limiter state is older than its configured retention boundary and no active window requires it
- **THEN** cleanup removes the state without affecting active counters
