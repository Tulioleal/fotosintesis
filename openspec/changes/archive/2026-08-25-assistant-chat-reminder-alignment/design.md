## Context

`classifier.py:386-395` reads reminder fields from raw classifier output while `CARE_CLASSIFIER_SCHEMA` (classifier.py:17-48) declares none; production output can never carry them (test fakes inject them at `tests/test_assistant_agent_part7.py:63-75`). `nodes.py:199` defaults missing recurrence to `"none"` and creates. The assistant repository's `create_reminder` performs no future-date check and no duplicate lookup (`assistant/repository.py:115-162`). `_extract_due_at` stamped UTC regardless of user tz (`graph_shared.py:124-129`) — a timezone quick-fix has landed, but free-text extraction remains a creation source. The frontend maps actions through `normalizeReminderAction` regexes (`AssistantChat.tsx`, `RemindersManager.tsx:990`) despite the reminders spec forbidding frontend semantic mappings, and derives date/time by slicing ISO `due_at`. `AssistantReminderSuggestion` lacks evidence/confidence/limitations carried by `ReminderSuggestionResult`. `requires_confirmation` exists but is ignored by the frontend.

## Goals / Non-Goals

**Goals:**

- One validation contract for reminder creation, whether from page flow or chat.
- Schema-validated classifier output as the only way the chat branch activates.
- Evidence-parity suggestion payloads and confirmation gating in chat.
- Eliminate frontend semantic rewriting and datetime string surgery.

**Non-Goals:**

- No changes to the reminders page suggestion generator (already backend-grounded).
- No new recurrence values or scheduling semantics.
- No notification/delivery changes.
- No confirmation-card UI redesign beyond payload wiring.

## Decisions

- **Classifier owns the fields or nothing does.** Add the four reminder fields to `CARE_CLASSIFIER_SCHEMA` as nullable/optional with prompt instructions; forbidden-extra-field validation guarantees the branch fires only on validated output. Free-text extraction (`_extract_due_at`) is demoted to a repair-time hint, never a creation source.
- **Clarification over defaults.** Missing recurrence/action/date/time produces the existing missing-data clarification naming the specific fields; no creation with implicit `"none"`.
- **Shared validation core.** Extract future-date check, effective-timezone resolution, and duplicate equivalence into logic used by both `POST /reminders` and the assistant create path (direct call, not HTTP self-call). Duplicates return the existing reminder reference.
- **Local time in, UTC instant out.** The graph carries explicit local date/time plus effective IANA timezone; conversion happens once in the shared core, DST-safe. Frontend receives explicit local fields.
- **Payload parity.** `AssistantReminderSuggestion` gains evidence context, confidence, limitations, justification, timezone — mirroring `ReminderSuggestionResult`.
- **Confirmation gating.** When `requires_confirmation` is true the frontend renders the confirmation card with duplicate-acceptance protection; direct creation only for explicit, complete, validated requests.
- **Frontend stops rewriting semantics.** Delete `normalizeReminderAction` from the chat acceptance path; actions arrive as schema-validated enum values.

## Risks / Trade-offs

- Classifier reliability bounds branch availability → conservative: invalid/absent fields degrade to clarification, never creation.
- Shared-core refactor touches the manual path → covered by existing reminders tests plus new parity tests.
- Stale conversations lack evidence fields → schema fields nullable during transition; new suggestions always populate them.

## Migration Plan

1. Ship schema+prompt extension; prove branch reachable only via validated fields.
2. Land shared validation core; switch assistant creation onto it.
3. Extend suggestion schema; regenerate TS contracts; update chat UI wiring.
4. Remove frontend rewriting utilities from the chat path.
5. Rollback: frontend revert restores prior rendering; backend additions are backward-compatible.

## Open Questions

- Shared validation core: reusable service both paths call, or assistant path invokes the reminders repository directly?
- Classifier reminder fields: strictly required when `intent == reminder_request`, or optional-with-null across all intents?
- `requires_confirmation` default: true for all chat suggestions (conservative) or classifier/request-driven?
