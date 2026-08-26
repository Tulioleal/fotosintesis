## Purpose

Define validation behavior for assistant-created plant-care reminders.
## Requirements
### Requirement: Explicit assistant reminder schedule

The assistant SHALL create plant-care reminders only when the user request includes a selected plant, a reminder action, an explicit due date, an explicit due time and an explicit recurrence. Assistant-created reminders SHALL satisfy the same validation contract as the manual reminders API: due instants SHALL be resolved from local date and time in the effective IANA timezone (reminder override when present, otherwise the stored user timezone), past due dates SHALL be rejected, and an equivalent active reminder SHALL be returned instead of duplicated via a transactional recheck. The assistant SHALL NOT default a missing recurrence to a non-recurring value and SHALL NOT create from free-text timestamp extraction alone.

#### Scenario: Reminder request missing recurrence

- WHEN the user asks the assistant to create a reminder with a plant, action, date and time but no recurrence
- THEN the assistant asks for the missing recurrence before creating the reminder
- AND the assistant does not create a non-recurring reminder by default

#### Scenario: Past due date is rejected like the manual API

- WHEN an assistant reminder request resolves to a past instant in the effective timezone
- THEN creation is rejected with an English validation message consistent with the manual reminders API

#### Scenario: Duplicate creation returns the existing reminder

- WHEN an equivalent active reminder already exists for the plant, action, and schedule
- THEN the assistant creation path returns a reference to the existing reminder after a transactional recheck
- AND no duplicate reminder row is inserted

#### Scenario: Due instant respects the effective timezone

- WHEN the assistant resolves a reminder due date and time for a user with a stored non-UTC timezone
- THEN the stored UTC instant corresponds to the local wall-clock value in that effective timezone

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

