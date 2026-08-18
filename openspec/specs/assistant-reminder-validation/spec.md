## Purpose

Define validation behavior for assistant-created plant-care reminders.

## Requirements

### Requirement: Explicit assistant reminder schedule

The assistant SHALL create plant-care reminders only when the user request includes a selected plant, a reminder action, an explicit due date, an explicit due time and an explicit recurrence.

#### Scenario: Reminder request missing explicit time

- **WHEN** the user asks the assistant to create a reminder with a date and recurrence but no explicit time
- **THEN** the assistant asks for the missing time before creating the reminder

#### Scenario: Reminder request missing recurrence

- **WHEN** the user asks the assistant to create a reminder with a plant, action, date and time but no recurrence
- **THEN** the assistant asks for the missing recurrence before creating the reminder

#### Scenario: Complete reminder request

- **WHEN** the user asks the assistant to create a reminder with plant, action, date, time and recurrence
- **THEN** the assistant calls the reminder creation tool with the explicit due timestamp and recurrence

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
