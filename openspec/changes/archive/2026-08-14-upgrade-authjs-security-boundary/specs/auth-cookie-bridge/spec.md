## ADDED Requirements

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
