## MODIFIED Requirements

### Requirement: Reminder lifecycle

The system SHALL allow users to create, list, edit, delete and complete plant-care reminders. All user-facing reminder lifecycle error messages SHALL be in English.

#### Scenario: Manual reminder created

- **WHEN** the user submits valid plant, action, date, time and recurrence values
- **THEN** the system saves the reminder and shows it in the reminders list

#### Scenario: Reminder not found

- **WHEN** a reminder lookup, edit, deletion or completion request targets a reminder that does not exist or does not belong to the authenticated user
- **THEN** the system returns a 4xx error whose user-facing message is in English and identifies the missing or unauthorized reminder

#### Scenario: Reminder mutation rejected with English error

- **WHEN** a reminder create, update or completion request is rejected because the request is invalid, the plant is unconfirmed, the date is in the past, or the recurrence is unsupported
- **THEN** the system returns a 4xx error whose user-facing message is in English and identifies the specific validation cause

### Requirement: Reminder validation

The system SHALL prevent invalid reminder creation with specific validation messages in English.

#### Scenario: Invalid reminder form

- **WHEN** the user submits missing plant, missing action, past date, empty time or invalid recurrence
- **THEN** the system blocks saving and displays the corresponding English validation message
