## Purpose

Defines manual and suggested plant-care reminders, recurrence, lifecycle actions, and notification permission fallback behavior.
## Requirements
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

### Requirement: Timezone-aware scheduling

The system SHALL resolve every reminder schedule in an effective IANA timezone taken from the reminder override when present, otherwise from the stored user timezone, and SHALL reject creation without any resolvable timezone. The creation interface SHALL treat the stored user timezone as the default and MAY expose a per-reminder override as an advanced option; the override MUST NOT be a required field.

#### Scenario: Creation uses the account timezone by default

- **WHEN** a user creates a reminder without selecting a timezone
- **THEN** the schedule resolves in the stored user timezone

#### Scenario: Override remains available as an advanced option

- **WHEN** the creation or edit form exposes the timezone control
- **THEN** it is presented as optional and collapsed behind advanced options on the create form

### Requirement: DST-safe recurrence

The system SHALL calculate recurring occurrences in the reminder's effective timezone so daily and weekly reminders preserve their local wall-clock time across DST transitions.

#### Scenario: Weekly reminder keeps local time across DST

- **WHEN** a weekly recurring reminder crosses a DST transition
- **THEN** the next occurrence keeps the same local wall-clock time in the effective timezone

#### Scenario: Daily reminder keeps local time

- **WHEN** a daily recurring reminder crosses a DST transition
- **THEN** the next occurrence keeps the same local wall-clock time in the effective timezone

#### Scenario: Monthly reminder clamps in local time

- **WHEN** a monthly recurring reminder targets a day that does not exist in the next month
- **THEN** the system clamps to the last day of that month in the effective timezone

### Requirement: Reminder counter integrity

Creation, completion, deletion, and plant reassignment SHALL update garden plant pending reminder counters within the same transaction as the reminder mutation.

#### Scenario: Moving a pending reminder updates both counters

- **WHEN** a pending reminder is moved to another plant
- **THEN** the source plant's pending count is decremented and the destination plant's pending count is incremented in the same transaction

#### Scenario: Moving a completed reminder does not change counters

- **WHEN** a completed reminder is moved to another plant
- **THEN** no pending reminder counters change

#### Scenario: Lifecycle mutations update the counter exactly once

- **WHEN** a pending reminder is created, completed, or deleted
- **THEN** the affected plant's pending count changes by exactly one in the same transaction

### Requirement: Reminder counter reconciliation

The system SHALL provide an idempotent reconciliation operation that recomputes each garden plant's active reminder count from its pending reminder rows.

#### Scenario: Reconciliation repairs seeded inconsistency

- **WHEN** a garden plant's stored active reminder count does not match its pending reminder rows
- **THEN** running reconciliation sets the stored count to the number of pending reminders for that plant

### Requirement: Backend-generated reminder suggestions

AI-labeled reminder suggestions SHALL originate from a backend operation that accepts a selected garden plant and an optional user request, resolves the plant's confirmed taxonomy through existing ownership checks, and loads profile evidence, garden location, notes, active reminders, and timezone before proposing a suggestion. The frontend SHALL NOT generate AI-labeled suggestions with local semantic regular expressions or fixed calendar defaults, and SHALL NOT rewrite, normalize, or remap backend-supplied action values through local semantic mappings on any acceptance surface, including assistant chat.

#### Scenario: Chat acceptance preserves backend semantics

- WHEN the user accepts an assistant-origin reminder suggestion from chat
- THEN the creation request carries the backend-supplied action value unchanged
- AND no client-side regex or keyword mapping alters the action before creation

### Requirement: Reminder suggestion duplicate detection

The system SHALL detect equivalent active reminders before returning a suggestion and SHALL recheck duplicates during creation. Equivalence considers the garden plant, the schema-validated action intent, and schedule overlap.

#### Scenario: Equivalent reminder already pending

- **WHEN** an equivalent pending reminder already exists for the same garden plant and schedule
- **THEN** the backend returns a reference to the existing reminder instead of a duplicate draft

#### Scenario: Duplicate rechecked at creation

- **WHEN** a suggestion is accepted and creation runs
- **THEN** the creation endpoint rechecks for duplicates transactionally to avoid races

### Requirement: Efficient next pending reminder selection

The system SHALL select each garden plant's earliest pending reminder without issuing one reminder request per garden plant. Completed and cancelled reminders SHALL be excluded from next-reminder selection.

#### Scenario: Next reminder reflects earliest pending row

- **WHEN** a garden plant has multiple pending reminders
- **THEN** the selected next reminder is the one with the earliest due instant

#### Scenario: Completed and cancelled reminders excluded

- **WHEN** a garden plant has only completed or cancelled reminders
- **THEN** no next-reminder summary is returned for that plant

#### Scenario: Single batched selection for garden list

- **WHEN** a garden list is retrieved for many plants
- **THEN** next-reminder summaries are resolved with a batched selection rather than one query per plant

