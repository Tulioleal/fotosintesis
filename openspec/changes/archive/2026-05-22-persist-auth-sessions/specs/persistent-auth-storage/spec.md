## ADDED Requirements

### Requirement: Database-backed auth repository
The system SHALL store authentication users, password hashes, sessions and recovery tokens in the configured database instead of process memory.

#### Scenario: Registered user is persisted
- **WHEN** a user registers with valid name, email and password
- **THEN** the system persists the user record with normalized email, Argon2id password hash and `email_verified` set to false

#### Scenario: Auth state survives repository boundaries
- **WHEN** a user is created and a later request is handled by a new repository instance or application dependency scope
- **THEN** the system can still find the user and verify credentials from persisted storage

### Requirement: Persisted session validation
The system SHALL create, refresh, validate and invalidate authenticated sessions using persisted session records.

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

### Requirement: Persisted recovery tokens
The system SHALL persist password recovery initiation tokens in the configured database while keeping user-facing recovery responses neutral.

#### Scenario: Recovery token is stored for existing email
- **WHEN** a recovery request is submitted with a syntactically valid email for an existing user
- **THEN** the system stores a recovery token with expiration linked to that user and returns the neutral confirmation message

#### Scenario: Recovery request remains neutral for missing email
- **WHEN** a recovery request is submitted with a syntactically valid email that does not match a user
- **THEN** the system returns the same neutral confirmation message without exposing account existence

### Requirement: Auth persistence tests
The implementation SHALL include automated tests that prove database-backed authentication persistence behavior.

#### Scenario: Backend persistence tests run
- **WHEN** backend tests run
- **THEN** they cover persisted user registration, credential verification, session validation, logout invalidation and recovery-token persistence
