## Purpose

Define the security boundary that keeps backend session credentials server-only while allowing authenticated frontend access to protected business data.

## Requirements

### Requirement: Backend session tokens remain server-only
The system SHALL keep opaque backend session tokens out of browser-readable frontend session state.

#### Scenario: Session data is read in the browser
- **WHEN** a client component reads the active session with Auth.js client APIs
- **THEN** the session data does not include the backend session token or any equivalent bearer credential

#### Scenario: Auth.js callback stores session metadata
- **WHEN** Auth.js builds the browser-visible session payload
- **THEN** it includes only safe user-facing identity and auth status fields

### Requirement: Protected frontend data calls use a server-side boundary
The system SHALL call protected backend business endpoints from server-side frontend code that can read HttpOnly session state.

#### Scenario: Home summary is requested by the browser
- **WHEN** the Home screen needs summary data
- **THEN** the browser calls a frontend-owned endpoint or server action rather than calling the backend with a session bearer token

#### Scenario: Server-side boundary calls backend
- **WHEN** the frontend server handles a protected business data request
- **THEN** it forwards the HttpOnly backend session cookie or equivalent server-only credential to the backend

#### Scenario: Backend session is missing or invalid
- **WHEN** the server-side boundary receives no valid authenticated session
- **THEN** it returns an unauthorized response without exposing backend credential details

### Requirement: Client code does not send backend session bearer tokens
The frontend SHALL NOT send opaque backend session tokens from client components or browser-executed API helpers.

#### Scenario: Protected client request is made
- **WHEN** browser-executed code requests Home summary or another protected backend business resource
- **THEN** it does not set `Authorization: Bearer <backend session token>`

### Requirement: Secure logout boundary
The system SHALL invalidate backend sessions without exposing the backend session token to browser JavaScript.

#### Scenario: User logs out
- **WHEN** an authenticated user signs out
- **THEN** the backend session is invalidated through a server-side boundary and Auth.js frontend auth state is cleared

### Requirement: Session boundary regression tests
The implementation SHALL include automated tests for token non-exposure and protected data access through the server-side boundary.

#### Scenario: Frontend tests run
- **WHEN** frontend tests run
- **THEN** they verify browser-visible session data does not contain the backend session token and Home loads through the server-side boundary
