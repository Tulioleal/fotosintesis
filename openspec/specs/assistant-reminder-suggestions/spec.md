## Purpose

Defines the user confirmation and creation flow for reminder suggestions originating from assistant conversations.

## Requirements

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

### Requirement: Reminder suggestions use redesigned assistant card treatment

Assistant-origin reminder suggestions SHALL keep their confirmation behavior while using the redesigned Fotosíntesis assistant card treatment.

#### Scenario: Reminder suggestion card follows assistant visual system

- **WHEN** an assistant chat response includes a reminder suggestion requiring confirmation
- **THEN** the redesigned frontend displays the suggestion in a tokenized Fotosíntesis card associated with the assistant response
- **AND** the card still shows the plant, action, due date and time, recurrence, and suggestion justification

#### Scenario: Reminder suggestion acceptance behavior is preserved

- **WHEN** the user accepts an assistant-origin reminder suggestion from the redesigned card
- **THEN** the frontend creates the reminder through the existing reminders API with the same payload mapping
- **AND** duplicate acceptance is disabled while creation is in progress

#### Scenario: Reminder suggestion states remain accessible

- **WHEN** a reminder suggestion is being accepted, accepted, or fails to create
- **THEN** the redesigned card communicates the in-progress, success, or failure state with accessible text and Fotosíntesis pending, success, or error styling
- **AND** existing button names are preserved unless explicitly updated by this spec
