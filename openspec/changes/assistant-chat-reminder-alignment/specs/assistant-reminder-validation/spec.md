## MODIFIED Requirements
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