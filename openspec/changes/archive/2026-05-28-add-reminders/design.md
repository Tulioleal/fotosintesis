## Context

This slice adds care scheduling for confirmed plants and assistant/profile suggestions. It should not require notification permission to preserve reminder data.

## Goals / Non-Goals

**Goals:**

- Support manual reminder creation and lifecycle actions.
- Support recurring next-occurrence calculation.
- Allow AI suggestions with clear justification and user confirmation.
- Preserve reminders when push permissions are rejected.

**Non-Goals:**

- No native mobile push infrastructure beyond web permission handling unless already available.
- No automatic reminder creation without user confirmation.

## Decisions

- Reminder records include plant, action, date, time, recurrence, status and suggestion justification.
- Suggested reminders can originate from profile, garden context or assistant conversation but require confirmation.
- Permission rejection affects notifications only, not reminder persistence.

## Risks / Trade-offs

- Recurrence edge cases can be complex; MVP should implement a constrained recurrence model.
- Suggested reminders must avoid implying certainty when profile evidence is weak.
