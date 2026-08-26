## Why

The reminders page currently labels browser-generated heuristics as AI suggestions, deriving actions with regular expressions and assigning fixed calendar defaults (tomorrow, 09:00, weekly). The assistant already supports review and confirmation cards, but its suggestion path does not combine profile evidence, garden conditions, light, and duplicates. Suggestion generation must be centralized in the backend and accurately represented.

## What Changes

- Add a backend operation dedicated to reminder suggestion generation.
- Remove the local `buildSuggestions` and `suggestActionFor` generation behavior from the frontend.
- Accept a selected garden plant and an optional explicit user request.
- Load confirmed taxonomy, profile evidence, garden location, and user notes.
- Load active reminders before proposing an equivalent action.
- Load a valid light measurement only when semantic classification requires it.
- Produce schema-validated suggestions through the configured assistant model.
- Require clarification when date, time, or recurrence information is missing.
- Return evidence context, confidence, limitations, and concise justification.
- Preserve explicit user confirmation before reminder creation.
- Preserve suggestion justification after the reminder is accepted.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `reminders`: Backend-generated, evidence-aware suggestions replace frontend heuristics.
- `assistant-reminder-suggestions`: Shared suggestion and confirmation contract grounded in evidence.
- `assistant-reminder-validation`: Validate complete, explicit suggestion payloads.
- `assistant-agent`: Generate structured suggestions from contextual evidence.

## Impact

- Add backend request and response schemas for suggestion or clarification results.
- Add an authenticated API (and frontend BFF route if required by current boundaries).
- Reuse assistant structured output and reminder confirmation rendering.
- Update generated OpenAPI TypeScript contracts.
- Replace reminders-page heuristic tests with backend interaction tests.
- Add metrics for accepted, edited, rejected, clarified, and duplicate suggestions.
