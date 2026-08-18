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

### Requirement: Reminder suggestions reuse bounded light context

Reminder suggestions originating from assistant conversations SHALL include light context only when the same owner- and plant-scoped eligibility policy for recommendation use allows it. Suggestion justification SHALL disclose the measurement source, age, and reliability in the same bounded way as care answers, and SHALL NOT include stale, unreliable, or foreign-plant readings.

#### Scenario: Eligible light context appears in suggestion justification

- **WHEN** a reminder suggestion includes light context that passes the shared eligibility policy
- **THEN** the suggestion justification discloses the measurement source, age, and reliability in the same bounded way as care answers

#### Scenario: Ineligible or foreign reading is omitted

- **WHEN** the only available readings are stale, unreliable, or associated with a different plant
- **THEN** the reminder suggestion does not include those readings as light context

### Requirement: Timezone-aware reminder suggestions

Assistant-origin reminder suggestions SHALL carry an effective IANA timezone through display and acceptance so the created reminder schedules at the intended local time.

#### Scenario: Suggestion carries effective timezone

- **WHEN** an assistant chat response includes a reminder suggestion requiring confirmation
- **THEN** the suggestion includes the effective IANA timezone used to interpret its due date and time

#### Scenario: Accepted suggestion schedules in effective timezone

- **WHEN** the user accepts an assistant-origin reminder suggestion
- **THEN** the system creates the reminder through the reminders API using the suggestion's effective timezone and local date and time

### Requirement: Evidence-grounded reminder suggestion contract

Reminder suggestions SHALL include the evidence context used to derive them, a confidence indication, limitations, and a concise justification. The justification SHALL persist with the created reminder.

#### Scenario: Suggestion returns evidence context

- **WHEN** the backend returns a reminder suggestion
- **THEN** the suggestion includes the evidence context used to derive it, confidence, limitations, and a concise justification

#### Scenario: Justification persists on acceptance

- **WHEN** the user accepts a suggestion
- **THEN** the created reminder stores the suggestion justification
