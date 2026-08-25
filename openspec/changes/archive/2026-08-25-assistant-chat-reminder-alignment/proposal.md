## Why

The chat reminder path is unreachable and misaligned with the page-flow rails. The reminder branch reads `reminder_action`/`reminder_recurrence`/`reminder_due_at`/`reminder_suggestion_requested` from raw classifier output, but the declared classifier schema never includes those fields and the prompt never requests them, so only test fakes can trigger creation. Missing recurrence silently defaults to "none" and creates immediately, contradicting the assistant-reminder-validation spec. The direct-create path skips the future-date and duplicate checks that `POST /reminders` enforces, stamps UTC while ignoring the user's timezone, and the frontend rewrites the action via regexes and slices ISO strings — exactly the semantic frontend mapping the reminders spec forbids. Chat suggestions also lack the evidence/confidence/limitations payload page-flow suggestions carry, and the `requires_confirmation` flag is ignored.

## What Changes

- Declare the reminder scheduling fields (`reminder_action`, `reminder_recurrence`, `reminder_due_at`, `reminder_suggestion_requested`) in the closed classifier schema and request them in the classifier prompt, making the chat branch reachable through validated output only.
- Replace silent recurrence defaulting with structured clarification requesting the missing recurrence.
- Route assistant reminder creation through the same validation contract as `POST /reminders`: future-date validation, transactional duplicate recheck, and effective-timezone resolution (reminder override else stored user timezone).
- Stamp `reminder_due_at` from local date/time in the effective timezone instead of unconditional UTC.
- Align `AssistantReminderSuggestion` with the page-flow suggestion payload: evidence context, confidence, limitations, justification, and effective timezone.
- Honor `requires_confirmation` in the frontend: flagged suggestions render as confirmation cards, never auto-create.
- Remove frontend semantic rewriting: delete `normalizeReminderAction` usage on the chat acceptance path and stop slicing ISO datetimes; the backend supplies explicit local date/time/timezone values.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Classifier contract carries validated reminder scheduling fields.
- `assistant-reminder-suggestions`: Chat suggestion payloads reach evidence-parity and honor confirmation gating.
- `assistant-reminder-validation`: Creation achieves validation parity with the manual reminders API.
- `reminders`: No frontend semantic action rewriting on any suggestion acceptance surface, including chat.

## Impact

- `backend/app/assistant/graph/classifier.py` schema + prompt; forbidden-extra-field handling tightened.
- `backend/app/assistant/graph/nodes.py` `_handle_reminder`; assistant repository create path delegated to shared validation logic.
- `backend/app/assistant/schemas.py` `AssistantReminderSuggestion` extended; OpenAPI TypeScript contracts regenerated.
- `frontend/src/components/assistant/AssistantChat.tsx` acceptance path; removal of chat-path `normalizeReminderAction` usage and ISO slicing.
- Tests: reachable branch via schema-valid classifier fakes only, clarification-on-missing-recurrence, past-date rejection, duplicate return, DST/timezone correctness, payload parity.
