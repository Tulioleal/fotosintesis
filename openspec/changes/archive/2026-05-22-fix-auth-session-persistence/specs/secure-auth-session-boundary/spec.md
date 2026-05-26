## MODIFIED Requirements

### Requirement: Protected frontend data calls use a server-side boundary
The system SHALL call protected backend business endpoints from server-side frontend code that can read HttpOnly session state and validate backend persisted session authority.

#### Scenario: Home summary is requested by the browser
- **WHEN** the Home screen needs summary data
- **THEN** the browser calls a frontend-owned endpoint or server action rather than calling the backend with a session bearer token

#### Scenario: Server-side boundary calls backend
- **WHEN** the frontend server handles a protected business data request
- **THEN** it forwards the HttpOnly backend session cookie or equivalent server-only credential to the backend

#### Scenario: Backend session is missing or invalid
- **WHEN** the server-side boundary receives no valid authenticated session
- **THEN** it returns an unauthorized response without exposing backend credential details

#### Scenario: Backend session has been invalidated
- **WHEN** the server-side boundary resolves an Auth.js session but the backend persisted session is invalidated or expired
- **THEN** it treats the request as unauthenticated and returns unauthorized without exposing credential details

## ADDED Requirements

### Requirement: Private frontend routes validate backend persisted session
The system SHALL require a valid backend persisted session before allowing access to private frontend routes.

#### Scenario: Private route with valid backend session
- **WHEN** an authenticated navigation targets Home, identification, search, Mi Jardín, reminders, light meter or assistant with a valid backend persisted session
- **THEN** the system allows the route to render

#### Scenario: Private route with missing backend session
- **WHEN** a navigation targets a private frontend route without a backend session credential
- **THEN** the system redirects server-side to `/login`

#### Scenario: Private route with invalidated backend session
- **WHEN** a navigation targets a private frontend route with Auth.js state but the backend persisted session has been invalidated or expired
- **THEN** the system redirects server-side to `/login`

### Requirement: Backend session validation remains server-only
The system SHALL validate backend persisted session state for frontend route protection without exposing backend session credentials to browser JavaScript.

#### Scenario: Browser reads session after route validation
- **WHEN** browser code reads the Auth.js session after private route validation
- **THEN** the session data still excludes the backend session token or any equivalent bearer credential

#### Scenario: Client component requests protected data
- **WHEN** browser-executed code requests Home summary or another protected business resource
- **THEN** it does not set `Authorization: Bearer <backend session token>`
