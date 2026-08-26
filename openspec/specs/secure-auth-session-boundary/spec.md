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

### Requirement: Auth.js failures deny protected access

The frontend authentication boundary MUST treat missing or invalid Auth.js configuration, token decoding failures, callback validation failures, and backend session validation failures as unauthenticated outcomes, and MUST NOT authorize protected behavior from the existence of an authentication object alone.

#### Scenario: Auth.js secret is missing

- **WHEN** a private route or protected frontend endpoint is requested without a configured Auth.js secret
- **THEN** the request is treated as unauthenticated
- **AND** private navigation redirects to login or the protected endpoint returns unauthorized as appropriate
- **AND** a backend session cookie on the request does not bypass the missing configuration denial

#### Scenario: Auth.js token decoding fails

- **WHEN** the server-side token decoder rejects malformed, invalid, or undecodable Auth.js state
- **THEN** no backend authorization header is produced
- **AND** the protected request is denied rather than throwing an authenticated or fail-open result

#### Scenario: Backend session validation cannot establish authority

- **WHEN** backend session validation rejects the credential or fails to complete
- **THEN** private route access is denied even if stale Auth.js state exists

#### Scenario: Auth.js callback state is malformed

- **WHEN** initial JWT or browser-session callback state lacks the required concrete identity, validated backend credential, or valid session expiration
- **THEN** application-owned callback validation fails with a generic authentication error
- **AND** no authenticated browser session or protected authorization result is created

#### Scenario: Truthy authentication error object exists

- **WHEN** Auth.js returns or throws configuration or callback error state represented by a truthy object
- **THEN** protected behavior still requires a concrete credential accepted by persisted backend-session validation
- **AND** the error object's existence does not authorize the request

### Requirement: Authentication failures preserve credential confidentiality

Application-owned authentication failure handling SHALL NOT expose Auth.js secrets, cookies, JWTs, backend credentials, callback payloads, or raw decoder exception text to browser responses or application-owned logs.

#### Scenario: Configuration or decoding failure is observed

- **WHEN** the frontend denies authentication because configuration, callback validation, or token decoding failed
- **THEN** any server-side diagnostic uses only a bounded non-sensitive error category
- **AND** the response and logs contain none of the secret or credential values

### Requirement: Trusted authentication source identity

The frontend authentication boundary SHALL derive limiter source identity from the documented GKE ingress and proxy trust chain, SHALL forward only an application-authenticated opaque source key to the backend, and MUST NOT use arbitrary client-supplied forwarding headers as limiter identity.

#### Scenario: Request traverses the trusted ingress chain

- **WHEN** an authentication request reaches the frontend through the configured GKE ingress
- **THEN** the frontend derives the source from the configured trusted proxy position
- **AND** passes only a keyed opaque source identity to the internal backend request

#### Scenario: Client spoofs forwarding headers

- **WHEN** a client supplies additional or conflicting `Forwarded` or `X-Forwarded-For` values outside the trusted proxy contract
- **THEN** those values do not create an arbitrary limiter source identity or bypass an active limit

#### Scenario: Internal source assertion is forged

- **WHEN** a request reaches the backend without a valid application-authenticated source assertion
- **THEN** the backend does not trust its asserted source key
- **AND** applies the documented conservative missing-source policy

### Requirement: Auth.js POST abuse boundary

The frontend SHALL apply the shared authentication abuse policy to relevant unauthenticated Auth.js POST operations without changing protected session reads, safe callback routing, or logout invalidation semantics.

#### Scenario: Relevant Auth.js POST operation is limited

- **WHEN** a configured unauthenticated Auth.js POST category exhausts its source-aware limit
- **THEN** the frontend rejects the operation with the bounded retry contract before expensive or state-changing authentication work

#### Scenario: Authenticated session operation continues

- **WHEN** a valid authenticated user performs session reading or logout and no operation-specific control rejects it
- **THEN** existing server-only credential handling and persisted-session invalidation behavior remain unchanged
