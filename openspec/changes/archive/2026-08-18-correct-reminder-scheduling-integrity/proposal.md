## Why

Reminder forms submit local date and time without an explicit timezone, and the backend interprets them as UTC. Recurring reminders can fire at the wrong local time or drift across DST, and moving a pending reminder between plants leaves counter rows inconsistent.

## What Changes

- Persist an IANA timezone preference on the user and an optional IANA timezone override on each reminder.
- Require an effective timezone (reminder override, else user preference) when scheduling.
- Convert submitted local date/time to an unambiguous UTC instant in the backend.
- Preserve local wall-clock recurrence across DST transitions.
- Define recoverable handling for ambiguous and nonexistent local times.
- Return the effective timezone with reminder responses for display and editing.
- Update source and destination plant counters transactionally when a reminder moves.
- Reconcile `active_reminders` values from pending reminder rows via an operational command.
- Mark legacy rows without reinterpreting existing instants.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reminders`: Explicit timezone scheduling, DST-safe recurrence, and transactional counter integrity.
- `assistant-reminder-suggestions`: Return timezone-aware suggestions.
- `plant-profile-garden`: Maintain accurate reminder summaries and reconcile counters.
- `persistent-auth-storage`: Persist the user's IANA timezone preference.

## Impact

- Add `timezone` columns and migration policy to users and reminders.
- Update reminder and suggestion request/response schemas and generated frontend contracts.
- Update recurrence calculation in the reminder repository and assistant suggestion parsing.
- Update frontend forms, displays, and validation.
- Add a counter reconciliation command.
- Add tests for timezone override, DST boundaries, plant reassignment, and backfill.
