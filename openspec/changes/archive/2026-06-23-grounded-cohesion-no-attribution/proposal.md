## Why

The current `_grounded_answer_prompt` (backend/app/assistant/graph.py) instructs the model to embed URLs and labeled "Source-backed:" blocks directly in the response prose. This produces visually fragmented outputs and leaks source metadata that is already available in the structured `AssistantChatResponse.sources[]` field. Source attribution in the text duplicates a channel the frontend already owns, with no functional justification, and makes the assistant voice feel disjointed. At the same time, the prompt also forces a strict per-sentence separation between source-backed and general-guidance statements, which the change softens to a continuous narrative with linguistic connectors. The change unifies the response voice and moves source handling entirely to the structured `sources[]` channel.

## What Changes

- Rewrite `_grounded_answer_prompt` in `backend/app/assistant/graph.py` so the final prose is continuous, fluid, and free of URLs, institution names, and "Source-backed / Fuentes / References" blocks.
- Delete the `attribution_instruction` injection for `evidence_type == "structured_api"`; `evidence_type` continues to be fed into the prompt for internal reasoning but no longer translates into an output instruction.
- Replace the strict per-sentence separation rule with soft linguistic connectors (`As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`) that signal general model guidance inside the narrative.
- Rewrite the per-status guidance rules for `partial` and `contradictory` to use generic phrasing (no URLs, no institution names, no suggestion to consult specific links).
- Add an explicit prohibition on URLs, institution names, and "Source-backed/Sources/References" blocks in the prose.
- Add two new tests in `backend/tests/test_assistant_agent.py`: a prompt-shape test that asserts the prohibitions and connectors are present, and an end-to-end test that mocks `tools.generate_text` to emit a buggy output containing `Source-backed: https://…` and asserts the final `content` does not include URLs or labels while `sources[]` does.
- **BREAKING**: The textual output shape of the grounded answer changes. Users who rely on in-prose URLs or "Source-backed:" markers will no longer see them. Sources continue to be available in the structured `sources[]` field; downstream consumers must rely on that field for attribution.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: The `RAG-grounded answers` and `Aspect-gated care answer synthesis` requirements change so the grounded-answer prompt prohibits URLs, institution names, and source labels in the prose, replaces the strict per-sentence separation with soft linguistic connectors, removes the structured-API attribution instruction, and uses generic phrasing for partial and contradictory states. Source attribution continues to live in the structured `sources[]` channel.

## Impact

- `backend/app/assistant/graph.py` — rewrite of the body of `_grounded_answer_prompt` and removal of the `attribution_instruction` branch.
- `backend/tests/test_assistant_agent.py` — two new tests (prompt-shape and end-to-end) plus variants for full/partial/contradictory and institution leakage.
- No changes to `schemas.py`, `service.py`, `tools.py`, `core/`, `providers/`, frontend, or evaluation.
- The `llm_general_guidance_used` diagnostic flag is preserved.
- Users will see continuous prose without in-text source labels; sources remain available in the structured response field.
