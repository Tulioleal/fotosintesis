## Context

The reminders page (`frontend/src/components/reminders/RemindersManager.tsx`) generates "AI suggestions" locally via `buildSuggestions` and `suggestActionFor`, which derive actions with regular expressions and assign fixed defaults (tomorrow, 09:00, weekly). The backend assistant graph already produces schema-validated structured output, loads evidence, and supports confirmation cards, but no backend path turns that into a reminder suggestion. Suggestion generation must move to the backend so it can use confirmed taxonomy, profile evidence, light context, and duplicate checks.

Dependencies already delivered: `use-light-context-in-care-guidance` (bounded light context), `correct-reminder-scheduling-integrity` (timezone, recurrence, counters), and `upgrade-authjs-security-boundary` (auth security).

## Goals / Non-Goals

**Goals:**

- Generate reminder suggestions in the backend from contextual evidence.
- Return schema-validated suggestions or structured clarification, never invented defaults.
- Detect equivalent active reminders before and during creation.
- Preserve explicit user confirmation and justification storage.
- Remove frontend regex-based suggestion generation.

**Non-Goals:**

- No push-notification delivery.
- No automatic reminder creation from profile updates.
- No deterministic multilingual action keyword mappings.
- No replacement of manual reminder creation.

## Decisions

- **Single backend suggestion operation** returns a discriminated result: a complete suggestion, a structured clarification request, or a duplicate reference to an existing reminder. The frontend renders each without local generation logic.
- **Structured model output for semantics.** Action intent and duplicate equivalence come from schema-validated model output, not regexes or keyword lists. Deterministic code is limited to schema validation, enum validation, ownership checks, and non-empty checks, per project constraints.
- **Reuse existing contracts.** The assistant's structured-output and reminder-confirmation card contracts are reused unchanged where possible; only the suggestion source changes.
- **Evidence assembly mirrors the care-answer path.** Confirmed taxonomy, profile evidence, garden location, notes, active reminders, timezone, and (only when semantically relevant) a valid light measurement are loaded and passed to the model. Nickname/display name are not treated as taxonomy.
- **Clarification over defaults.** Missing date, time, timezone, or recurrence produces a structured clarification response with the missing fields; no suggestion is presented as ready until complete. Recurrence is always explicit, including an explicit non-recurring value.
- **Duplicate policy.** Equivalence considers garden plant, normalized action intent (semantic), and schedule overlap. The backend returns an existing reminder reference instead of a duplicate draft, and the creation endpoint rechecks duplicates transactionally to avoid races.
- **Provenance returned with the suggestion.** Each suggestion includes evidence context, confidence, limitations, and a concise justification; the justification persists with the created reminder.

## Risks / Trade-offs

- Model suggestions overstate evidence → constrain via schema and returned evidence metadata.
- Duplicate detection races → final transactional recheck in the creation endpoint.
- Sensitive notes leak into logs → logs exclude notes and generated suggestion content.
- Provider failure blocks suggestions → return retry and manual creation paths.
- Existing chat behavior regresses → share contracts without replacing the confirmation UI.

## Migration Plan

1. Add the backend suggestion endpoint and schemas behind the existing authenticated boundary.
2. Update generated OpenAPI TypeScript contracts.
3. Replace the reminders-page local generators with calls to the backend endpoint.
4. Remove `buildSuggestions`/`suggestActionFor` and their tests; add backend interaction tests.
5. Rollback is a frontend revert plus disabling the new endpoint; no data migration is involved.

## Open Questions

None.
