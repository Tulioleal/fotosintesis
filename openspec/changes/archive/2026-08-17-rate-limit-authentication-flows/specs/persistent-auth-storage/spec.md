## ADDED Requirements

### Requirement: Shared persistent limiter state

When database-backed rate limiting is configured, the system SHALL store opaque authentication limiter keys and expiring windows in shared persistent storage using atomic bounded updates that are visible to every application replica.

#### Scenario: Concurrent requests consume one limit

- **WHEN** concurrent matching authentication requests update one limiter window through separate repository instances
- **THEN** atomic storage operations allow no more requests than the configured bound
- **AND** all instances observe the same resulting state

#### Scenario: Limiter record is stored

- **WHEN** a covered request consumes a persistent limit
- **THEN** the stored record contains only an opaque keyed digest, endpoint category, bounded count, and window timestamps required for enforcement
- **AND** contains no password, token, raw account identifier, or raw source address

### Requirement: Persistent limiter retention and cleanup

The system SHALL index limiter expiry and provide idempotent bounded cleanup that removes expired limiter records without deleting active windows.

#### Scenario: Cleanup runs concurrently with requests

- **WHEN** cleanup executes while active windows are being updated
- **THEN** expired records are removed in bounded batches
- **AND** active limiter decisions remain atomic and enforceable
