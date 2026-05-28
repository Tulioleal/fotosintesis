## Context

The assistant can classify reminder intent and either ask for missing fields or create a reminder directly when the request includes plant, action, due date, due time and recurrence. The frontend assistant chat consumes `requires_confirmation`, but it only renders the assistant message and sources; it does not receive or display a structured reminder suggestion that the user can accept.

The reminders UI already creates reminders through the existing reminders API and stores `suggestion_justification`. This change should reuse that API rather than introducing a separate confirmation endpoint or persistence model.

## Goals / Non-Goals

**Goals:**

- Return structured assistant-origin reminder suggestions when the assistant needs user confirmation instead of immediate creation.
- Render a confirmation card in the assistant conversation with plant, action, due date/time, recurrence and justification.
- Create accepted assistant suggestions through the existing reminder creation API.
- Preserve current direct assistant reminder creation when the user's request is explicit enough to create immediately.

**Non-Goals:**

- No new reminder database table or separate suggestion persistence lifecycle.
- No automatic creation of assistant-origin suggestions without an explicit user action in the UI.
- No broad redesign of assistant conversation history or reminder scheduling semantics.

## Decisions

- Extend the assistant chat response with an optional `reminder_suggestion` object instead of encoding suggestion details inside message text. This keeps the UI deterministic and avoids parsing Spanish assistant copy.
- Build the suggestion from the same extracted fields used for reminder creation: selected garden plant, action, due timestamp, recurrence and justification. If required fields are missing, the assistant continues asking for them instead of returning an incomplete suggestion card.
- Keep acceptance client-side by calling `createReminder` with the suggestion payload. This reuses existing validation, persistence, cache invalidation behavior and `suggestion_justification` storage.
- Leave `requires_confirmation` as a high-level signal for the UI, but treat the presence of `reminder_suggestion` as the actionable confirmation payload.

## Risks / Trade-offs

- Assistant and frontend reminder payloads can drift -> share the same API-client reminder create type on the frontend and keep backend response fields aligned with generated OpenAPI schemas.
- A suggested due timestamp may be displayed incorrectly if timezone handling is inconsistent -> send an ISO timestamp and derive the form date/time from that value in one frontend helper.
- Users may submit the same suggestion more than once -> disable the accept action while creation is pending and show success feedback after creation.
- Conversation history will not persist pending suggestion objects unless separately stored -> acceptable for this slice because the response payload is immediately actionable; persisted suggestion history is out of scope.
