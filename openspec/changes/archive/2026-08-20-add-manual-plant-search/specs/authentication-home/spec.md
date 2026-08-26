## MODIFIED Requirements

### Requirement: Placeholder access for pending features

The system SHALL expose navigable authenticated placeholders for private features that are outside this slice.

#### Scenario: Pending feature opened

- **WHEN** an authenticated user opens identification, light meter, reminders, My Garden or assistant before that feature is implemented
- **THEN** the system shows a protected placeholder screen with a "Coming soon" copy in English
- **AND** the system does not implement real feature logic in this slice

#### Scenario: Search is a real protected flow

- **WHEN** an authenticated user opens the search route
- **THEN** the system renders the functional search experience rather than a "Coming soon" placeholder
