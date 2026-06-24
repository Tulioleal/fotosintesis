## MODIFIED Requirements

### Requirement: Password recovery initiation

The system SHALL allow users to initiate password recovery from the authentication screen. The recovery response message SHALL be in English.

#### Scenario: Recovery requested

- **WHEN** a user requests recovery with a valid email format
- **THEN** the system generates and persists a recovery token with expiration when applicable
- **AND** shows a neutral English confirmation

#### Scenario: Recovery without email provider

- **WHEN** the recovery request is completed in this slice
- **THEN** the system does not send an email
- **AND** the recovery token and confirmation contract remain prepared for a later email provider integration
- **AND** the neutral English confirmation is the same as in the recovery-requested scenario

### Requirement: Home mobile-first

The system SHALL show an authenticated mobile-first Home with access to identification, search, light meter, reminders, My Garden and assistant. The home access labels returned by `GET /home/summary` SHALL be in English.

#### Scenario: Home opens for authenticated user

- **WHEN** an authenticated user opens `/home`
- **THEN** the system fetches `GET /home/summary`
- **AND** shows primary identification CTA, secondary feature access and bottom navigation with the active Home section

#### Scenario: Home summary contract

- **WHEN** Home data loads successfully
- **THEN** the response includes the authenticated user, empty-state information and access metadata for identification, search, light meter, reminders, My Garden and assistant
- **AND** the `HomeAccessItem.label` values for these access entries are in English: `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, `Assistant`

#### Scenario: Home server state

- **WHEN** the frontend fetches Home data
- **THEN** it uses TanStack Query for loading, cache, retry and error state

### Requirement: Unauthenticated private frontend access

The system SHALL redirect unauthenticated users to `/login` for private routes. The list of private routes includes Home, identification, search, My Garden, reminders, light meter and assistant.

#### Scenario: Unauthenticated private frontend access

- **WHEN** a navigation targets Home, identification, search, My Garden, reminders, light meter or assistant without a valid session
- **THEN** the system redirects server-side to `/login`

### Requirement: Placeholder access for pending features

The system SHALL expose navigable authenticated placeholders for private features that are outside this slice.

#### Scenario: Pending feature opened

- **WHEN** an authenticated user opens identification, search, light meter, reminders, My Garden or assistant before that feature is implemented
- **THEN** the system shows a protected placeholder screen with a "Coming soon" copy in English
- **AND** the system does not implement real feature logic in this slice

### Requirement: Bottom navigation

The system SHALL provide bottom navigation for the main mobile-first product sections.

#### Scenario: Bottom navigation renders

- **WHEN** an authenticated user views Home or a placeholder private route
- **THEN** the bottom navigation shows Home, Identify, My Garden, Reminders and Assistant
- **AND** the active section is visually indicated
