## 1. Assistant Reminder Validation

- [x] 1.1 Update `_handle_reminder` to treat missing recurrence as required reminder input and include it in the clarification response.
- [x] 1.2 Update `_extract_due_at` so date-only reminder requests return `None` instead of defaulting to `09:00`.
- [x] 1.3 Ensure complete reminder requests still call `reminder_create` with the parsed due timestamp and recurrence.

## 2. Tests

- [x] 2.1 Add a backend assistant test proving date-only reminder requests require clarification and do not create a reminder.
- [x] 2.2 Add a backend assistant test proving missing recurrence requires clarification and does not create a reminder.
- [x] 2.3 Run the assistant backend test module and fix regressions.
