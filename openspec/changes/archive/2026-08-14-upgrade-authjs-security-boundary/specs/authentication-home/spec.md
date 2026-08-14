## ADDED Requirements

### Requirement: Patched and reproducible Auth.js dependency

The frontend SHALL pin `next-auth` to exact version `5.0.0-beta.32`, SHALL NOT declare `@auth/core` directly, and SHALL resolve one compatible transitive Auth.js core version from the committed lockfile.

#### Scenario: Reproducible authentication dependencies are installed

- **WHEN** the frontend production dependencies are installed from the committed lockfile
- **THEN** the installed `next-auth` version is exactly `5.0.0-beta.32`
- **AND** no direct `@auth/core` dependency is present
- **AND** exactly one transitive `@auth/core` version is reachable

#### Scenario: A vulnerable Auth.js resolution is proposed

- **WHEN** dependency verification finds `next-auth` in the GHSA-8fpg-xm3f-6cx3 affected range through `5.0.0-beta.31`
- **THEN** verification fails before merge or deployment

### Requirement: Validated credentials authentication result

The Auth.js credentials provider SHALL create authenticated state only from a schema-valid successful backend response containing a concrete user identity and non-empty server-only backend session credential.

#### Scenario: Backend credentials response is valid

- **WHEN** backend credential verification succeeds with all required user, session token, and session expiration fields in their valid shapes
- **THEN** Auth.js creates the existing authenticated JWT session state
- **AND** the browser-visible session continues to exclude the backend session credential

#### Scenario: Successful backend response is malformed

- **WHEN** backend credential verification returns a successful HTTP response with invalid JSON, a missing identity field, a missing or empty session token, or an invalid session expiration
- **THEN** Auth.js denies authentication
- **AND** no partially authenticated user or browser-visible backend credential is created

#### Scenario: Existing credentials journey is preserved

- **WHEN** a valid user logs in, follows a safe callback URL, reads the active session, and logs out
- **THEN** login, callback routing, session persistence, backend-session invalidation, and frontend state clearing preserve their existing behavior
