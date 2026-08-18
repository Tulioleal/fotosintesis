## Purpose

Define durable database storage for authentication identities, sessions,
recovery tokens, and shared authentication limiter state across application
instances.

## Requirements

### Requirement: Database-backed auth repository

The system SHALL store authentication users, password hashes, sessions and recovery tokens in the configured database instead of process memory.

#### Scenario: Registered user is persisted

- **WHEN** a user registers with valid name, email and password
- **THEN** the system persists the user record with normalized email, Argon2id password hash and `email_verified` set to false

#### Scenario: Auth state survives repository boundaries

- **WHEN** a user is created and a later request is handled by a new repository instance or application dependency scope
- **THEN** the system can still find the user and verify credentials from persisted storage

### Requirement: Persisted session validation

The system SHALL create, refresh, validate and invalidate authenticated sessions using persisted session records, and frontend private access SHALL depend on that persisted session validity.

#### Scenario: Credential verification persists session

- **WHEN** a registered user submits valid credentials
- **THEN** the system creates a persisted opaque session record with idle expiration and absolute expiration

#### Scenario: Protected endpoint validates persisted session

- **WHEN** a request targets a protected backend endpoint with a valid persisted session token
- **THEN** the backend authorizes the request and refreshes the session expiration within the absolute maximum lifetime

#### Scenario: Invalidated session is rejected

- **WHEN** a user logs out and then reuses the same session token against a protected backend endpoint
- **THEN** the backend rejects the request with `401`

#### Scenario: Missing or expired session is rejected

- **WHEN** a request targets a protected backend endpoint without a session token or with an expired session token
- **THEN** the backend rejects the request with `401`

#### Scenario: Frontend private route rejects invalidated session

- **WHEN** a user navigates to a private frontend route after the backend persisted session is invalidated or expired
- **THEN** the frontend redirects server-side to `/login`

#### Scenario: Frontend private route accepts valid persisted session

- **WHEN** a user navigates to a private frontend route with a valid backend persisted session
- **THEN** the frontend allows the private route to render

### Requirement: Persisted recovery tokens

The system SHALL persist password recovery initiation tokens in the configured database as a one-way hash only, keeping user-facing recovery responses neutral. A valid token SHALL be consumable exactly once before expiration.

#### Scenario: Recovery token hash is stored for existing email

- **WHEN** a recovery request is submitted with a syntactically valid email for an existing user
- **THEN** the system stores only a one-way hash of the token with expiration and unused state linked to that user
- **AND** returns the neutral confirmation message
- **AND** the raw token exists only long enough to build the delivery link

#### Scenario: Recovery request remains neutral for missing email

- **WHEN** a recovery request is submitted with a syntactically valid email that does not match a user
- **THEN** the system returns the same neutral confirmation message without exposing account existence

#### Scenario: New token invalidates prior active tokens

- **WHEN** a new recovery token is created for an account with active tokens
- **THEN** the system invalidates the prior active tokens for that account

#### Scenario: Persisted record excludes raw token

- **WHEN** persisted recovery records are inspected
- **THEN** they contain no raw usable token, only the token hash, user, creation time, expiry, and use state

### Requirement: Atomic recovery confirmation

The system SHALL validate, consume, and apply a recovery confirmation in one atomic operation so that password update and token consumption are committed together and concurrent attempts produce at most one success.

#### Scenario: Confirmation commits atomically

- **WHEN** a valid confirmation consumes a token and updates the password
- **THEN** the token hash lookup, consumption, and password update are committed in a single transaction

#### Scenario: Concurrent confirmation yields one success

- **WHEN** two concurrent confirmation attempts submit the same valid token
- **THEN** at most one attempt succeeds and the other fails neutrally

### Requirement: Session revocation on password reset

The system SHALL revoke all active persisted sessions for an account after a successful password reset.

#### Scenario: Pre-reset sessions stop authorizing

- **WHEN** a recovery confirmation succeeds
- **THEN** the system revokes all active sessions for the account
- **AND** subsequent protected requests using pre-reset session tokens are rejected with `401`

#### Scenario: New session remains unaffected

- **WHEN** the user logs in again after a successful reset
- **THEN** the new session authorizes protected requests normally

### Requirement: Auth persistence tests

The implementation SHALL include automated tests that prove database-backed authentication persistence behavior, one-time recovery token consumption, session revocation after password reset, and frontend rejection of stale persisted sessions.

#### Scenario: Backend persistence tests run

- **WHEN** backend tests run
- **THEN** they cover persisted user registration, credential verification, session validation, logout invalidation, recovery-token hashing, recovery consumption, session revocation, and one-time replay rejection

#### Scenario: Frontend session persistence tests run

- **WHEN** frontend tests run
- **THEN** they cover private route rejection when the backend persisted session is missing, expired or invalidated despite stale Auth.js state

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

### Requirement: Persisted user timezone preference

The system SHALL persist the user's IANA timezone preference on the authenticated user record and SHALL expose it as the default effective timezone for reminder scheduling.

#### Scenario: Timezone preference is persisted

- **WHEN** the user saves a valid IANA timezone preference
- **THEN** the system persists it on the user record and returns it on subsequent authenticated reads

#### Scenario: Missing timezone preference

- **WHEN** the user has not saved a timezone preference
- **THEN** the system returns no default timezone and reminder scheduling falls back to the reminder override or a recoverable error
