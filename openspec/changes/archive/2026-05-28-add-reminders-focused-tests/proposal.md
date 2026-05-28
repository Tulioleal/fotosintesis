## Why

Reminder management currently lacks focused regression coverage across the UI, API route, and repository boundaries. Adding targeted tests now reduces risk around reminder creation, updates, deletion, loading states, and persistence behavior without changing product functionality.

## What Changes

- Add focused frontend component tests for `frontend/src/components/reminders/RemindersManager.tsx`.
- Add backend route tests for `backend/app/api/reminders.py` covering expected request and response behavior.
- Add backend repository tests for `backend/app/reminders/repository.py` covering persistence operations and edge cases.
- Keep runtime application behavior unchanged; this change only adds test coverage.

## Capabilities

### New Capabilities
- `reminders-test-coverage`: Focused test coverage for reminder UI, API route, and repository behavior.

### Modified Capabilities

## Impact

- Affected frontend test files for reminder component behavior.
- Affected backend test files for reminder route and repository coverage.
- No API contract, database schema, dependency, or runtime behavior changes are expected.
