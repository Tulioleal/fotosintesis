## ADDED Requirements

### Requirement: Timezone-aware reminder suggestions

Assistant-origin reminder suggestions SHALL carry an effective IANA timezone through display and acceptance so the created reminder schedules at the intended local time.

#### Scenario: Suggestion carries effective timezone

- **WHEN** an assistant chat response includes a reminder suggestion requiring confirmation
- **THEN** the suggestion includes the effective IANA timezone used to interpret its due date and time

#### Scenario: Accepted suggestion schedules in effective timezone

- **WHEN** the user accepts an assistant-origin reminder suggestion
- **THEN** the system creates the reminder through the reminders API using the suggestion's effective timezone and local date and time
