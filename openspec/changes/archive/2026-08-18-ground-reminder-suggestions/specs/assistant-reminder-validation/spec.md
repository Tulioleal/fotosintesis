## ADDED Requirements

### Requirement: Explicit suggestion schedule

A reminder suggestion SHALL identify the plant, action, date, time, and timezone, and SHALL include an explicit recurrence value, including an explicit non-recurring value. The system SHALL NOT invent tomorrow, 09:00, or weekly as defaults.

#### Scenario: Suggestion has explicit schedule fields

- **WHEN** the backend returns a complete reminder suggestion
- **THEN** the suggestion identifies the plant, action, date, time, timezone, and an explicit recurrence value

#### Scenario: Missing schedule fields produce clarification

- **WHEN** date, time, timezone, or recurrence is missing
- **THEN** the backend returns a structured clarification response requesting the missing fields
- **AND** no suggestion draft is presented as ready for acceptance

#### Scenario: No fixed defaults

- **WHEN** scheduling fields are absent
- **THEN** the system does not default to tomorrow, 09:00, or weekly recurrence
