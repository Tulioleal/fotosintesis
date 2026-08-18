## ADDED Requirements

### Requirement: Timezone-aware scheduling

The system SHALL require an effective IANA timezone when scheduling a reminder and SHALL convert the submitted local date and time to a UTC instant in that timezone. The effective timezone is the reminder's timezone override when present, otherwise the user's stored timezone.

#### Scenario: Reminder resolves to correct UTC instant

- **WHEN** the user submits a valid plant, action, local date, local time, and an effective IANA timezone
- **THEN** the system stores a UTC instant that corresponds to that local wall-clock value in that timezone

#### Scenario: Reminder timezone override wins

- **WHEN** a reminder supplies a timezone override that differs from the user's stored timezone
- **THEN** the system schedules using the reminder override

#### Scenario: Missing effective timezone

- **WHEN** the user submits a reminder with no reminder timezone and no stored user timezone
- **THEN** the system returns a 4xx error whose user-facing message is in English and asks for a timezone

#### Scenario: Invalid timezone

- **WHEN** the submitted timezone is not a valid IANA timezone
- **THEN** the system returns a 4xx error whose user-facing message is in English

#### Scenario: Nonexistent local time

- **WHEN** the submitted local time falls inside a DST spring-forward gap in the effective timezone
- **THEN** the system returns a recoverable validation error listing the surrounding valid local times

#### Scenario: Ambiguous local time

- **WHEN** the submitted local time falls inside a DST fall-back overlap and no explicit offset choice is provided
- **THEN** the system applies a documented deterministic rule (the earlier offset) to resolve the instant

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
