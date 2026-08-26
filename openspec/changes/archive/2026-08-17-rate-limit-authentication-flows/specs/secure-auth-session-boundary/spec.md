## ADDED Requirements

### Requirement: Trusted authentication source identity

The frontend authentication boundary SHALL derive limiter source identity from the documented GKE ingress and proxy trust chain, SHALL forward only an application-authenticated opaque source key to the backend, and MUST NOT use arbitrary client-supplied forwarding headers as limiter identity.

#### Scenario: Request traverses the trusted ingress chain

- **WHEN** an authentication request reaches the frontend through the configured GKE ingress
- **THEN** the frontend derives the source from the configured trusted proxy position
- **AND** passes only a keyed opaque source identity to the internal backend request

#### Scenario: Client spoofs forwarding headers

- **WHEN** a client supplies additional or conflicting `Forwarded` or `X-Forwarded-For` values outside the trusted proxy contract
- **THEN** those values do not create an arbitrary limiter source identity or bypass an active limit

#### Scenario: Internal source assertion is forged

- **WHEN** a request reaches the backend without a valid application-authenticated source assertion
- **THEN** the backend does not trust its asserted source key
- **AND** applies the documented conservative missing-source policy

### Requirement: Auth.js POST abuse boundary

The frontend SHALL apply the shared authentication abuse policy to relevant unauthenticated Auth.js POST operations without changing protected session reads, safe callback routing, or logout invalidation semantics.

#### Scenario: Relevant Auth.js POST operation is limited

- **WHEN** a configured unauthenticated Auth.js POST category exhausts its source-aware limit
- **THEN** the frontend rejects the operation with the bounded retry contract before expensive or state-changing authentication work

#### Scenario: Authenticated session operation continues

- **WHEN** a valid authenticated user performs session reading or logout and no operation-specific control rejects it
- **THEN** existing server-only credential handling and persisted-session invalidation behavior remain unchanged
