## 1. Data Model and Migration

- [x] 1.1 Add a nullable `timezone` column to the `users` table and a nullable `timezone` column to the `reminders` table with a migration that does not shift existing instants.
- [x] 1.2 Update the user schema to accept, validate, and return an IANA timezone preference.
- [x] 1.3 Add an optional `timezone` override to reminder create/update request schemas and an effective `timezone` to reminder DTO responses.

## 2. Scheduling Conversion

- [x] 2.1 Add a helper that validates an IANA timezone and converts local date/time to a UTC instant using `zoneinfo`.
- [x] 2.2 Resolve the effective timezone as reminder override first, then user preference, and reject with an English validation error when neither exists.
- [x] 2.3 Handle nonexistent local times with a recoverable validation error and ambiguous local times with the documented fold rule.

## 3. Recurrence

- [x] 3.1 Rewrite next-occurrence calculation to add one wall-clock day/week/month in the effective timezone, then convert back to UTC.
- [x] 3.2 Keep monthly day clamping in local time.

## 4. Counter Integrity

- [x] 4.1 Update plant reassignment to decrement the source and increment the destination only for pending reminders, in the same transaction.
- [x] 4.2 Ensure create, complete, and delete counter updates remain in the same transaction as the reminder mutation.

## 5. Reconciliation

- [x] 5.1 Add an idempotent reconciliation command that sets each garden plant's active reminder count from its pending reminder rows.

## 6. Assistant Suggestions

- [x] 6.1 Include the effective IANA timezone in suggestion display and acceptance payloads.

## 7. Frontend

- [x] 7.1 Add a user timezone preference field and a reminder timezone override field to forms.
- [x] 7.2 Display reminder due times using the effective timezone and update generated contracts.

## 8. Verification

- [x] 8.1 Add backend tests for timezone override, missing timezone, invalid timezone, DST boundaries, ambiguous and nonexistent local times, and monthly clamping.
- [x] 8.2 Add backend tests for plant reassignment counter updates and reconciliation backfill.
- [x] 8.3 Run backend and frontend lint, typecheck, and test suites.
