## 1. Frontend Reminder Component Tests

- [x] 1.1 Add `frontend/src/components/reminders/RemindersManager.test.tsx` using existing Vitest, Testing Library, query-client, API client mock, and `next/navigation` mock patterns.
- [x] 1.2 Cover loading and empty garden states, including disabled creation when no garden plants are available.
- [x] 1.3 Cover form validation for missing required fields and non-future date/time without invoking create or update mutations.
- [x] 1.4 Cover successful reminder creation, query invalidation effects, notification permission messaging, and success notice rendering.
- [x] 1.5 Cover editing an existing pending reminder and submitting an update payload with the selected reminder id.
- [x] 1.6 Cover completing and deleting reminders, including the API calls and user-visible notices.
- [x] 1.7 Cover accepting a generated suggestion and mutation/query failure rendering.

## 2. Backend Reminder Route Tests

- [x] 2.1 Add route tests for `backend/app/api/reminders.py` using existing async `httpx` ASGI and authenticated user setup conventions.
- [x] 2.2 Cover authenticated create, list, update, complete, and delete flow with expected status codes and response bodies.
- [x] 2.3 Cover ownership scoping so another user's plants or reminders are not accessible.
- [x] 2.4 Cover past due-date validation and not-found responses for unknown plants or reminders.
- [x] 2.5 Cover unauthenticated access rejection for reminder endpoints.

## 3. Backend Reminder Repository Tests

- [x] 3.1 Add repository tests for `backend/app/reminders/repository.py` using the existing in-memory async database fixture.
- [x] 3.2 Cover create and list behavior, including plant display data, filter behavior, ordering, and active reminder count increment.
- [x] 3.3 Cover garden ownership checks for create and update attempts against another user's garden plant.
- [x] 3.4 Cover partial update behavior preserving omitted fields.
- [x] 3.5 Cover delete behavior for pending reminders, including active reminder count decrement and missing-reminder return values.
- [x] 3.6 Cover complete behavior for non-recurring and recurring reminders, including completed status, next occurrence creation, `next_occurrence_at`, and already-completed stability.

## 4. Verification

- [x] 4.1 Run the targeted frontend test file with `pnpm test -- RemindersManager.test.tsx` from `frontend`.
- [x] 4.2 Run the targeted backend reminder tests with `pytest tests/test_reminders.py` from `backend` or the final chosen reminder test file names.
- [x] 4.3 Run broader affected suites if targeted tests reveal shared helper or fixture changes.
