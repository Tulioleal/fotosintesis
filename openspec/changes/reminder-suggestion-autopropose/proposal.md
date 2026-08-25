## Why

The AI suggestion flow currently dead-ends: the generation prompt orders the model to leave date/time/recurrence null when the user has not stated them, so "Generar con IA" (which sends only the plant) frequently returns a clarification card demanding fecha, hora and zona horaria — exactly the manual entry the feature was meant to replace. Timezone is also over-exposed on the page: a per-reminder selector in the create form plus an account preference card defaulting to "Sin definir", even though every backend path already resolves the stored account timezone automatically.

## What Changes

- Stage-2 generation MUST propose a concrete local date, time and recurrence derived from the task type, plant profile cadence, eligible light data, location/notes and current local time — each proposal carrying its one-sentence justification. Nulls are reserved for genuinely undeterminable fields.
- The model no longer produces the timezone: the backend resolves it server-side from the stored user timezone (existing effective-timezone rule). Clarification lists "timezone" only when the account has none.
- Suggestion card gains "Editar antes de guardar": opens the creation form pre-filled from the proposal (plant, task type, date, time, recurrence) for tweaking before the existing confirmed create. Acceptance stays immediate-create.
- Optional free-text context input feeding the existing `request` field.
- Create form: Zona horaria selector moves under a collapsed "Opciones avanzadas" block; "Mi Zona Horaria" preference prefills from browser detection with a device-detected hint; the AI action is promoted as the primary entry above the manual form.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-reminder-suggestions`: Generation proposes a justified concrete schedule instead of clarifying by default; timezone resolved server-side.
- `reminders`: Creation form surfaces advanced timezone override as optional; account timezone remains the single source of defaults.

## Impact

- `backend/app/reminders/suggestions.py`: `_SUGGESTION_SCHEMA` (drop timezone), `_suggestion_prompt`, `suggest()` zone resolution, `_missing_schedule_fields`.
- `frontend/src/components/reminders/RemindersManager.tsx` (+scss, tests): edit-before-save prefill, request input, advanced collapse, tz prefill, ordering/promotion.
- Spec deltas only; API contracts unchanged (`request` field already exists).
