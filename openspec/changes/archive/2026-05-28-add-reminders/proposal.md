## Why

Users need actionable care follow-up after identifying or saving plants. Reminders provide manual and AI-suggested care scheduling while preserving user confirmation and notification fallbacks.

## What Changes

- Implement reminder data model with plant, action, date, time, recurrence, status and suggestion justification.
- Build manual reminder creation form with validation messages.
- Implement reminder list, edit, delete and complete actions.
- Implement recurring reminder next-occurrence calculation.
- Implement IA-suggested reminders from plant profile, garden context or assistant conversation.
- Request notification permissions and preserve reminders when permissions are rejected.

## Capabilities

### New Capabilities

- `reminders`: manual reminders, AI-suggested reminders, recurrence, completion and notification permission handling.

### Modified Capabilities

- None.

## Impact

- Affects reminder persistence, forms, list/detail actions, assistant/profile integrations and notification permission UX.
