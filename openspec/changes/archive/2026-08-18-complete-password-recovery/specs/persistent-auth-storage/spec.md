## MODIFIED Requirements

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

### Requirement: Auth persistence tests

The implementation SHALL include automated tests that prove database-backed authentication persistence behavior, one-time recovery token consumption, session revocation after password reset, and frontend rejection of stale persisted sessions.

#### Scenario: Backend persistence tests run

- **WHEN** backend tests run
- **THEN** they cover persisted user registration, credential verification, session validation, logout invalidation, recovery-token hashing, recovery consumption, session revocation, and one-time replay rejection

#### Scenario: Frontend session persistence tests run

- **WHEN** frontend tests run
- **THEN** they cover private route rejection when the backend persisted session is missing, expired or invalidated despite stale Auth.js state

## ADDED Requirements

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
