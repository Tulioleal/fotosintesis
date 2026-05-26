## MODIFIED Requirements

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

### Requirement: Auth persistence tests
The implementation SHALL include automated tests that prove database-backed authentication persistence behavior and frontend rejection of stale persisted sessions.

#### Scenario: Backend persistence tests run
- **WHEN** backend tests run
- **THEN** they cover persisted user registration, credential verification, session validation, logout invalidation and recovery-token persistence

#### Scenario: Frontend session persistence tests run
- **WHEN** frontend tests run
- **THEN** they cover private route rejection when the backend persisted session is missing, expired or invalidated despite stale Auth.js state
