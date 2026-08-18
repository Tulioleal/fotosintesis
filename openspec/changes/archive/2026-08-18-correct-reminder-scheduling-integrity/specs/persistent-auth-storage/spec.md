## ADDED Requirements

### Requirement: Persisted user timezone preference

The system SHALL persist the user's IANA timezone preference on the authenticated user record and SHALL expose it as the default effective timezone for reminder scheduling.

#### Scenario: Timezone preference is persisted

- **WHEN** the user saves a valid IANA timezone preference
- **THEN** the system persists it on the user record and returns it on subsequent authenticated reads

#### Scenario: Missing timezone preference

- **WHEN** the user has not saved a timezone preference
- **THEN** the system returns no default timezone and reminder scheduling falls back to the reminder override or a recoverable error
