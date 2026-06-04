## Why

The assistant already retrieves botanical evidence from RAG, structured plant-data APIs and trusted web fallback, but final user-facing botanical answers are assembled with fixed templates instead of the configured language model. This produces raw evidence summaries where the assistant should synthesize the user question, plant context and available evidence into a grounded, useful response.

## What Changes

- Add model-backed final answer synthesis for botanical assistant responses.
- Feed the model the user message, selected plant, topic, available evidence, limitations and source/provider metadata.
- Require generated answers to stay grounded in supplied evidence, avoid unsupported plant-care claims and communicate uncertainty when evidence is incomplete or degraded.
- Preserve existing source attribution in assistant API responses.
- Keep deterministic action flows such as reminders and light measurement lookup outside model synthesis unless they need botanical explanation.
- Add a deterministic fallback to the current summary style when model generation fails, recording the model failure as a non-blocking tool failure.
- Update assistant regression coverage for model invocation, grounding constraints, source preservation and fallback behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Botanical answer generation changes from direct template summaries to model-backed synthesis over retrieved or fallback evidence with grounded fallback handling.

## Impact

- Affects backend assistant orchestration in `backend/app/assistant/graph.py` and likely assistant tool/provider wiring in `backend/app/assistant/tools.py`.
- Uses the existing configured model provider from the provider registry; no new external provider dependency is expected.
- Updates assistant tests and fake tool/model behavior.
- No frontend response schema or public API shape change is expected.
