## ADDED Requirements

### Requirement: Assistant reminder suggestion confirmation

The system SHALL let users review and accept reminder suggestions that originate from assistant conversations before those reminders are created.

#### Scenario: Assistant suggestion displayed

- **WHEN** an assistant chat response includes a reminder suggestion requiring confirmation
- **THEN** the frontend displays a confirmation card with the plant, action, due date and time, recurrence and suggestion justification

#### Scenario: Assistant suggestion accepted

- **WHEN** the user accepts an assistant-origin reminder suggestion
- **THEN** the system creates the reminder through the existing reminders API and stores the suggestion justification

#### Scenario: Assistant suggestion acceptance in progress

- **WHEN** an assistant-origin reminder suggestion is being accepted
- **THEN** the frontend disables duplicate acceptance and shows the resulting success or failure state
