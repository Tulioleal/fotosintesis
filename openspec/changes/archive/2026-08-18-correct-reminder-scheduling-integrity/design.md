## Context

The reminder repository currently combines submitted local `date`/`time` using `timezone.utc` (`_combine_due_at`), so a user scheduling 09:00 in Argentina stores 09:00Z. Recurrence then adds a fixed `timedelta`, which ignores DST. `update_reminder` also reassigns `garden_plant_id` without adjusting either plant's `active_reminders`. There is no way to derive the user's intended timezone from existing rows.

## Goals / Non-Goals

**Goals:**

- Resolve new scheduling to a correct UTC instant using an explicit IANA timezone.
- Keep daily/weekly recurrence on the intended local wall-clock time across DST.
- Handle ambiguous and nonexistent local times deterministically and recoverably.
- Keep `active_reminders` consistent across create, complete, delete, and plant moves.
- Provide a reconciliation path that recomputes counters from pending rows.
- Preserve existing instants during migration.

**Non-Goals:**

- No push-notification delivery.
- No inference of historical timezone from IP or locale.
- No watering-event records or AI suggestion generation.

## Decisions

- **Use the standard library `zoneinfo`** for IANA validation and local-to-UTC conversion instead of adding a new dependency. An invalid zone string is rejected as a validation error.
- **Effective timezone = reminder override, else user preference.** New reminders require an effective timezone; if neither the reminder nor the user supplies one, creation fails with a recoverable English error.
- **Store only the UTC instant** (`due_at`) plus the resolved timezone on the reminder. The timezone column records which zone produced the instant so recurrence and display stay deterministic. This keeps the data model minimal.
- **Ambiguous local times use `fold=0`** (earlier offset) as the documented deterministic rule; the client may still pass an explicit `fold` choice. **Nonexistent local times return a recoverable validation error** listing the surrounding valid times, rather than silently shifting.
- **Recurrence is computed in the effective timezone** (add one wall-clock day/week/month), then converted back to UTC. Monthly uses the calendar-day clamp already present, applied in local time.
- **Counter mutations run in the same transaction as the reminder mutation.** A plant move decrements the source and increments the destination only when the reminder is pending; completed reminders do not change pending counters.
- **Migration adds nullable `timezone` columns.** A null reminder timezone marks legacy UTC interpretation and is never silently reinterpreted. A backfill command recomputes `active_reminders` independently of timezone migration.

## Risks / Trade-offs

- Legacy intent is unknowable → keep existing instants and treat null as legacy UTC.
- Browser timezone changes while traveling → persisted preference is explicit and stable.
- DST behavior is subtle → standard library + boundary fixtures in tests.
- Counter updates can race → run updates in the reminder transaction and add a reconciliation command.

## Migration Plan

1. Add nullable `users.timezone` and `reminders.timezone` columns; existing rows remain null (legacy UTC).
2. Deploy additive API fields (timezone in/out) before enforcing the requirement.
3. Run reconciliation as an idempotent command that sets each garden plant's `active_reminders` to the count of its pending reminders.
4. Rollback drops only the new columns; no existing instants are shifted.
