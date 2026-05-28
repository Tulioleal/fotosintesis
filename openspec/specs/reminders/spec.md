## Purpose

Defines manual and suggested plant-care reminders, recurrence, lifecycle actions, and notification permission fallback behavior.

## Requirements

### Requirement: Reminder lifecycle

The system SHALL allow users to create, list, edit, delete and complete plant-care reminders.

#### Scenario: Manual reminder created

- **WHEN** the user submits valid plant, action, date, time and recurrence values
- **THEN** the system saves the reminder and shows it in the reminders list

### Requirement: Reminder validation

The system SHALL prevent invalid reminder creation with specific validation messages.

#### Scenario: Invalid reminder form

- **WHEN** the user submits missing plant, missing action, past date, empty time or invalid recurrence
- **THEN** the system blocks saving and displays the corresponding validation message

### Requirement: Recurring reminders

The system SHALL calculate the next occurrence when a recurring reminder is completed.

#### Scenario: Recurring reminder completed

- **WHEN** the user completes a recurring pending reminder
- **THEN** the system records completion and schedules or exposes the next occurrence

### Requirement: AI-suggested reminders

The system SHALL support AI-suggested reminders from plant profile, garden context or assistant conversation and MUST require user confirmation before creation.

#### Scenario: Suggested reminder accepted

- **WHEN** the user accepts a suggested care reminder
- **THEN** the system creates the reminder and stores the suggestion justification

### Requirement: Notification permission fallback

The system SHALL preserve reminders when notification permissions are rejected.

#### Scenario: Notification permission rejected

- **WHEN** the user rejects notification permission
- **THEN** the reminder remains saved and the system explains notifications will not be sent
