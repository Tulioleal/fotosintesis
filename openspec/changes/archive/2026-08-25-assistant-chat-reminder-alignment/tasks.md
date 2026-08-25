## 1. Classifier Contract

- [x] 1.1 Add `reminder_action`, `reminder_recurrence`, `reminder_due_at`, `reminder_suggestion_requested` to `CARE_CLASSIFIER_SCHEMA` with types/enums/nullability matching downstream consumption.
- [x] 1.2 Update classifier prompt to request the fields only for reminder intents, null otherwise.
- [x] 1.3 Assert forbidden-extra-field validation still rejects undeclared reminder-like keys from non-schema sources.
- [x] 1.4 Rewrite tests that inject raw reminder fields to inject schema-valid classifier output instead.

## 2. Creation Validation Parity

- [x] 2.1 Extract future-date validation, effective-timezone resolution, duplicate equivalence into shared logic.
- [x] 2.2 Convert assistant create path to resolve local date/time in the effective timezone; reject past dates with English messages.
- [x] 2.3 Transactional duplicate recheck on assistant creation; return existing reference instead of inserting.
- [x] 2.4 Remove silent `"none"` defaulting in `nodes.py`; emit structured missing-data clarification naming missing fields.
- [x] 2.5 Demote `_extract_due_at` free-text parsing to a non-authoritative hint.

## 3. Suggestion Payload Parity

- [x] 3.1 Extend `AssistantReminderSuggestion` with evidence context, confidence, limitations, justification, effective timezone.
- [x] 3.2 Regenerate OpenAPI TypeScript contracts.
- [x] 3.3 Render evidence/limitations in the chat confirmation card alongside plant, action, schedule, justification.

## 4. Frontend Alignment

- [x] 4.1 Stop calling `normalizeReminderAction` on chat suggestion acceptance; send backend action unchanged.
- [x] 4.2 Stop slicing `due_at`; consume explicit local date, time, timezone fields.
- [x] 4.3 Honor `requires_confirmation`: flagged suggestions render confirmation cards with duplicate-acceptance protection; complete unflagged creations render as model-generated confirmations only.

## 5. Verification

- [x] 5.1 Test the branch is unreachable when classifier output lacks valid reminder fields (production-shaped fakes).
- [x] 5.2 Parity tests: identical create attempts via `POST /reminders` and chat produce identical validation outcomes (past date, duplicate, DST edge, missing timezone).
- [x] 5.3 Regression tests proving chat acceptance no longer mutates action client-side or derives dates from string slices.
- [x] 5.4 Backend + frontend lint/typecheck/tests green.
