## ADDED Requirements

### Requirement: Password recovery confirmation

The system SHALL allow a user to complete password recovery with a valid delivered token and a new password that satisfies the existing registration password policy. Confirmation SHALL remain neutral for unknown, expired, invalidated, or already-used tokens and SHALL NOT reveal token or account state.

#### Scenario: Valid token changes password once

- **WHEN** a user submits a valid unexpired token and a new password satisfying the password policy
- **THEN** the system hashes the new password with Argon2id
- **AND** persists the replacement password and consumes the token atomically

#### Scenario: Reused token fails

- **WHEN** a user submits an already-consumed token
- **THEN** the system rejects the attempt without changing the password again
- **AND** returns the same neutral response as any other invalid token

#### Scenario: Unknown, expired, or invalidated token fails

- **WHEN** a user submits a token that is unknown, expired, or invalidated
- **THEN** the system rejects the attempt with neutral behavior that does not distinguish the failure reason

#### Scenario: New password is rejected

- **WHEN** the submitted new password does not satisfy the existing registration password policy
- **THEN** the system rejects the request with a deterministic validation error
- **AND** does not consume the token

#### Scenario: Successful reset revokes sessions

- **WHEN** a recovery confirmation succeeds
- **THEN** the system revokes all active sessions for the account
- **AND** subsequent requests using pre-reset session tokens are rejected

#### Scenario: Confirmation is limited

- **WHEN** recovery confirmation is rejected for either a known or unknown token by the shared abuse policy
- **THEN** the response preserves the endpoint's neutral body contract and equivalent retry metadata

### Requirement: Recovery completion frontend

The system SHALL provide a frontend reset route that reads the token from the URL, collects a new password and confirmation, and returns the user to login with a neutral completion notice without revealing token-state details.

#### Scenario: Reset route reads the token

- **WHEN** a user opens the reset route with a token
- **THEN** the frontend reads the token without displaying it in page copy

#### Scenario: Reset form validates input

- **WHEN** a user edits the reset form
- **THEN** the frontend validates the new password and confirmation controls with accessible labels and errors

#### Scenario: Successful reset returns to login

- **WHEN** a valid reset completes successfully
- **THEN** the frontend returns the user to login with a neutral completion notice

#### Scenario: Invalid token stays neutral

- **WHEN** the reset request fails for an unknown, used, or expired token
- **THEN** the UI presents a neutral failure that does not distinguish the token detail
- **AND** offers a safe path to request a new recovery link
