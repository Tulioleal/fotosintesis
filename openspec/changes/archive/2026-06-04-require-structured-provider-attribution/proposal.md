## Why

Structured plant-data answers currently pass provider metadata into the grounded model prompt, but the assistant is not explicitly required to mention those structured provider sources in the generated response. This leaves source attribution dependent on model behavior instead of making it a contractual prompt requirement.

## What Changes

- Update grounded answer generation so `structured_api` prompts explicitly require the final response to mention the structured provider sources used.
- Preserve the existing source metadata returned in the assistant API response.
- Keep non-structured evidence prompts unchanged except for any shared wording needed to avoid regressions.
- Add regression coverage proving structured provider names are required in the prompt and remain available in the answer path.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Structured API-backed botanical answers must explicitly instruct model synthesis to mention structured provider sources in the user-facing answer.

## Impact

- Affects backend assistant prompt construction in `backend/app/assistant/graph.py`.
- Updates assistant regression tests for structured API prompt attribution.
- No API schema, provider interface or frontend change is expected.
