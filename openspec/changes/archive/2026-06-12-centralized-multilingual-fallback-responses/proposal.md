## Why

The assistant currently mixes deterministic orchestration with user-facing Spanish prose hardcoded across fallback and clarification paths. This causes inconsistent multilingual behavior, duplicated response logic, and brittle fallback UX even though the agent already tracks `answer_language` for grounded model-generated answers.

## What Changes

- Introduce a centralized fallback-response generation layer for all user-facing fallback paths.
- Replace rich hardcoded fallback prose with structured response intents, allowed facts, and safety constraints.
- Use the classified `answer_language` when rendering fallback responses with the language model.
- Preserve deterministic graph routing, evidence gating, answerability checks, source validation, and conservative safety decisions.
- Prevent the fallback-response generator from changing fallback intent, adding unsupported botanical facts, adding unsupported recommendations, or overriding safety constraints.
- Remove deterministic language detection from the assistant graph.
- Make the LLM classifier the source of `language` and `answer_language` when classification succeeds.
- Require the classifier to set `answer_language` from the actual language used by the user message, ignoring requests to answer in a different language.
- Default both `language` and `answer_language` to Spanish when deterministic routing is used after classifier failure, timeout, invalid output, forbidden extra fields, or low confidence.
- Return a minimal Spanish-only emergency response with no links and no unsupported botanical claims when fallback-response generation fails or returns empty text.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Changes fallback response generation, classifier language handling, deterministic language fallback behavior, and user-facing fallback consistency for the assistant agent.

## Impact

- Affected code: `backend/app/assistant/graph.py`, assistant care contracts if a new structured response draft type is added, assistant tests, and possibly provider prompts used by text generation.
- Affected behavior: user-facing fallback, clarification, action-failure, safety, missing-taxonomy, insufficient-evidence, partial-evidence, and model-failure responses.
- Affected diagnostics: `answer_language` remains exposed in assistant diagnostics, while fallback reason codes remain internal metadata.
- No API schema changes are expected unless implementation chooses to expose additional debug metadata.
- No new external service dependency is expected; the existing model provider is used for fallback-response rendering.
