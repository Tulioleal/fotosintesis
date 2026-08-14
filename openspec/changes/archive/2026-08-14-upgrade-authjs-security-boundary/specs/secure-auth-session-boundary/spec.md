## ADDED Requirements

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
