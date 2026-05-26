## MODIFIED Requirements

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
