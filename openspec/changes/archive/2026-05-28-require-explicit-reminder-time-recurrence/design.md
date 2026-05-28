## Context

The assistant reminder path lives in `backend/app/assistant/graph.py`. `_handle_reminder` gathers the selected plant, due date/time, action and recurrence before calling `reminder_create`. Today `_extract_due_at` accepts `YYYY-MM-DD` without a time and supplies `T09:00`, while recurrence is passed through even when `_extract_recurrence` returns `None`.

This change aligns the implementation with the reminder validation expectation that assistant-created reminders need explicit scheduling intent before persistence.

## Goals / Non-Goals

**Goals:**

- Block assistant reminder creation when the request lacks an explicit time.
- Block assistant reminder creation when the request lacks an explicit recurrence.
- Keep clarification messaging specific enough for the user to correct missing fields.
- Add focused backend tests that verify no reminder tool call is made for missing time or recurrence.

**Non-Goals:**

- Add natural-language date parsing beyond the current ISO date/time parser.
- Change reminder persistence schema or accepted recurrence values.
- Implement a one-off reminder mode.
- Change frontend reminder flows.

## Decisions

- Treat missing recurrence as incomplete input in `_handle_reminder` rather than normalizing it to a one-off value. This preserves the existing recurrence vocabulary and avoids introducing unmodeled persistence semantics.
- Change `_extract_due_at` to require both date and `HH:MM` time in the matched input. Returning `None` for date-only input lets the existing missing-field confirmation path handle the response.
- Keep validation in the assistant graph before the tool call. The assistant already owns conversational clarification, and avoiding the tool call makes failure behavior easier to test.
- Add tests at `AssistantGraph.run` level instead of only testing private helpers. This verifies user-visible clarification and tool-call suppression together.

## Risks / Trade-offs

- Date-only requests that previously created `09:00` reminders will now require a follow-up clarification. Mitigation: the clarification lists missing `fecha u hora` and `recurrencia`, matching existing assistant behavior for incomplete reminders.
- The current parser still only recognizes ISO-style dates and times. Mitigation: keep this change narrow and avoid expanding parsing scope without a separate natural-language scheduling design.
