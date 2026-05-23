## Purpose

Defines how frontend server boundaries bridge backend session credentials created during Auth.js credential login without exposing backend bearer credentials to browser JavaScript.

## Requirements

### Requirement: Backend credential survives login server-side
The system SHALL retain the backend session credential from successful credential login in server-only frontend state usable by frontend route handlers.

#### Scenario: Credentials login succeeds
- **WHEN** Auth.js verifies user credentials through the backend
- **THEN** the backend session credential is retained only in server-side state and is not exposed through browser-readable session data

#### Scenario: Browser reads Auth.js session after login
- **WHEN** browser code reads the Auth.js session payload
- **THEN** the payload does not include the backend session token or an equivalent backend bearer credential

### Requirement: Protected route handlers use login-created credential
The system SHALL allow frontend server route handlers to authenticate protected backend calls immediately after login without requiring browser JavaScript to handle the backend token.

#### Scenario: Home summary after login
- **WHEN** an authenticated browser requests `/api/home/summary` after credential login
- **THEN** the frontend server calls backend `GET /home/summary` with a server-only backend credential

#### Scenario: Backend cookie already exists
- **WHEN** a protected frontend route receives a valid backend session cookie
- **THEN** it MAY forward that HttpOnly cookie to the backend without exposing its value to client JavaScript

#### Scenario: No valid backend credential exists
- **WHEN** the frontend server cannot resolve a valid backend credential for a protected request
- **THEN** it returns an unauthorized response without exposing credential details

### Requirement: Logout invalidates login-created backend session
The system SHALL invalidate the backend session created during login through a server-side frontend boundary.

#### Scenario: User logs out after credentials login
- **WHEN** an authenticated user triggers logout after credential login
- **THEN** the frontend server calls backend `POST /auth/logout` with the server-only backend credential before Auth.js client state is cleared

### Requirement: Auth cookie bridge regression tests
The implementation SHALL include automated tests for the login-created credential bridge and browser non-exposure behavior.

#### Scenario: Frontend tests run
- **WHEN** frontend tests run
- **THEN** they verify protected route handlers can authenticate using login-created server-only state and browser session data does not contain backend credentials
