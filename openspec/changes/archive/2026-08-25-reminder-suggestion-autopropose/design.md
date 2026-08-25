## Context

`_suggestion_prompt` instructs: "Never invent tomorrow as the date, 09:00 as the time… leave that field null so the caller can ask for clarification." With an empty `request` (the only value the UI sends), Stage 2 returns nulls and `_missing_schedule_fields` yields the dead-end clarification. The schema also requires the model to emit a timezone, though the backend already resolves one from the account. Frontend exposes three timezone surfaces; the create-form selector duplicates the account preference.

## Goals / Non-Goals

**Goals:**

- Plant (+ optional context) → concrete justified proposal → human confirm/edit.
- Single timezone default source: stored account timezone; browser-detected prefill for the preference.
- No dead-end clarification for ordinary scheduling.

**Non-Goals:**

- No removal of the confirmation gate, duplicate recheck, or future-date validation.
- No hardcoded code-level calendar defaults (anti-heuristic rule stays; proposals are model-derived AND justified).
- No change to manual create semantics beyond collapsing the tz override.

## Decisions

- **Model proposes, backend anchors:** prompt receives current local date/time + zone key as grounding and MUST output date/time/recurrence with justification referencing its reasoning. `_missing_schedule_fields` keeps guarding nulls (clarification) but should be rare.
- **Timezone leaves the model contract:** dropped from `_SUGGESTION_SCHEMA`; service resolves via effective-timezone rule (stored account tz) and stamps it on the outcome. Unset account tz → clarification listing "timezone" pointing at the preference card.
- **Edit-before-save:** card action prefills the existing create form (task type matched case-insensitively against TASK_TYPES, else closest normalized label) and hides the suggestion panel; nothing auto-saves.
- **Timezone UI:** create form wraps the selector in a collapsed "Opciones avanzadas"; preference card prefills browser-detected IANA zone when account is unset.

## Risks / Trade-offs

- Model-proposed schedules can be wrong → justification is mandatory and rendered; edit-before-save plus post-hoc edit cover correction.
- Prompt drift toward always "tomorrow 9:00" → judged by rubric? Not gated here; mitigated by requiring derivation references in justification text.

## Migration Plan

1. Backend prompt/schema/service flip with tests.
2. Frontend card actions + collapse + prefills.
3. Rollback: revert prompt paragraph; frontend changes are additive.

## Open Questions

None blocking; acceptance-immediate confirmed by product.
