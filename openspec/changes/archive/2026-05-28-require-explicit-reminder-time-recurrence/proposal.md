## Why

Assistant-created reminders currently accept incomplete scheduling details: `_extract_due_at` silently defaults a date-only request to `09:00`, and `_handle_reminder` can create one-off reminders with no recurrence. This conflicts with the reminder validation contract and can create care reminders at times or repeat behavior the user did not explicitly choose.

## What Changes

- Require an explicit time in assistant reminder requests before calling the reminder creation tool.
- Require an explicit recurrence in assistant reminder requests before calling the reminder creation tool.
- Update due-date parsing so date-only reminder text is treated as incomplete instead of defaulting to `09:00`.
- Add backend tests for missing recurrence and missing explicit time to prevent incomplete reminder creation.

## Capabilities

### New Capabilities
- `assistant-reminder-validation`: Assistant reminder creation validation for explicit date, time, recurrence, plant and action values.

### Modified Capabilities
- None.

## Impact

- Affects `backend/app/assistant/graph.py` reminder extraction and validation.
- Affects `backend/tests/test_assistant_agent.py` assistant reminder tests.
- No database, API schema, dependency, or frontend changes are expected.
