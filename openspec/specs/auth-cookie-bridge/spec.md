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
The system SHALL allow frontend server route handlers to authenticate protected backend calls immediately after login without requiring browser JavaScript to handle the backend token, and SHALL treat backend persisted session validity as authoritative.

#### Scenario: Home summary after login
- **WHEN** an authenticated browser requests `/api/home/summary` after credential login
- **THEN** the frontend server calls backend `GET /home/summary` with a server-only backend credential

#### Scenario: Backend cookie already exists
- **WHEN** a protected frontend route receives a valid backend session cookie
- **THEN** it MAY forward that HttpOnly cookie to the backend without exposing its value to client JavaScript

#### Scenario: No valid backend credential exists
- **WHEN** the frontend server cannot resolve a valid backend credential for a protected request
- **THEN** it returns an unauthorized response without exposing credential details

#### Scenario: Login-created credential is no longer valid
- **WHEN** the frontend server resolves a login-created server-only credential that the backend rejects as expired or invalidated
- **THEN** it returns an unauthorized response without treating the Auth.js JWT alone as sufficient authentication

### Requirement: Logout invalidates login-created backend session
The system SHALL invalidate the backend session created during login through a server-side frontend boundary before clearing Auth.js frontend auth state.

#### Scenario: User logs out after credentials login
- **WHEN** an authenticated user triggers logout after credential login
- **THEN** the frontend server calls backend `POST /auth/logout` with the server-only backend credential before Auth.js client state is cleared

#### Scenario: User navigates after backend logout
- **WHEN** backend logout has invalidated the persisted session but stale Auth.js state remains temporarily present
- **THEN** private frontend route protection rejects the stale state and redirects to `/login`

### Requirement: Auth cookie bridge regression tests
The implementation SHALL include automated tests for the login-created credential bridge, browser non-exposure behavior and invalidated backend session behavior.

#### Scenario: Frontend tests run
- **WHEN** frontend tests run
- **THEN** they verify protected route handlers can authenticate using login-created server-only state and browser session data does not contain backend credentials

#### Scenario: Invalidated credential tests run
- **WHEN** frontend tests run
- **THEN** they verify stale Auth.js state does not authorize protected route handlers or private route access after the backend session is invalidated

### Requirement: Auth cookie bridge uses the aligned public JWT API

The frontend SHALL resolve login-created backend credentials through the public `next-auth/jwt` export and SHALL NOT import `@auth/core` directly in application or test source.

#### Scenario: Login-created JWT contains a backend credential

- **WHEN** a server-side frontend boundary decodes valid Auth.js state containing a non-empty backend credential
- **THEN** it may forward that credential to the backend over the existing server-only authorization path
- **AND** backend persisted session validation remains authoritative

#### Scenario: JWT state lacks a concrete backend credential

- **WHEN** decoded Auth.js state is missing `backendCredential` or contains a non-string or empty value
- **THEN** the bridge returns no backend authorization headers
- **AND** the protected request is unauthorized

#### Scenario: JWT decoder cannot produce valid state

- **WHEN** the public `next-auth/jwt` decoder fails because configuration or encoded state is invalid
- **THEN** the bridge returns no backend authorization headers
- **AND** no credential or decoder detail is exposed
