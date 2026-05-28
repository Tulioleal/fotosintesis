## Why

Assistant-origin reminder suggestions are not visible as an actionable confirmation flow in the chat UI. This leaves the existing reminder suggestion contract incomplete because users can accept profile/garden-context suggestions, while assistant conversation suggestions only surface as text or a generic confirmation flag.

## What Changes

- Add structured assistant reminder suggestions to assistant chat responses when the assistant has enough reminder details to propose, but not directly create, a reminder.
- Render assistant-origin suggested reminders in the chat confirmation UI with the plant, action, schedule, recurrence and justification.
- Allow users to accept a suggested reminder from the assistant UI, creating it through the existing reminders API and preserving the suggestion justification.
- Keep explicit reminder creation behavior intact when the user provides all required information and asks the assistant to create the reminder directly.

## Capabilities

### New Capabilities

- `assistant-reminder-suggestions`: User confirmation and creation flow for reminder suggestions originating from assistant conversations.

### Modified Capabilities

- `assistant-agent`: Assistant chat responses expose actionable reminder suggestions when user confirmation is required.

## Impact

- Backend assistant graph/service/schema response payloads for reminder suggestion metadata.
- Frontend assistant chat component and API client types for rendering and accepting suggestions.
- Existing reminders API remains the creation path; no new persistence model is required.
- Tests should cover structured assistant suggestion responses and frontend acceptance behavior.
