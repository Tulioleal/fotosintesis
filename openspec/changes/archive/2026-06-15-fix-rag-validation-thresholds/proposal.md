## Why

The backend applies a single evidence validation threshold (0.75) to all RAG judge results, causing structurally strong but lower-confidence answers (e.g., watering frequency with confidence 0.35) to be rejected and trigger expensive web fallback paths. This creates unnecessary latency, increases API costs, and degrades user experience for straightforward botanical questions where the RAG evidence is semantically valid. Additionally, long-running judge and web search calls can exceed frontend timeout limits, causing request failures.

## What Changes

- Add a context-aware validation threshold system that uses different thresholds for safety-sensitive aspects, strong full-support results, and partial/ambiguous cases.
- Introduce a "strong full support" detection helper that identifies structurally complete RAG results (status full, answerable, all aspects covered, source support present, no contradictions).
- Add configurable timeouts for the answerability judge and web search provider calls to prevent backend requests from exceeding frontend timeouts.
- Ensure valid RAG evidence with strong structure but lower confidence is accepted without triggering unnecessary web fallback.
- Preserve strict safety validation for pet_toxicity and human_edibility aspects.
- Add structured logging for threshold decisions to improve debuggability.

## Capabilities

### New Capabilities

- `rag-contextual-validation`: Context-aware evidence validation thresholds that distinguish safety-sensitive, strong full-support, and partial/ambiguous RAG results.

### Modified Capabilities

- `assistant-agent`: Validation logic in `_validate_evidence_against_required_aspects` changes to use contextual thresholds; `_judge_answerability` gains timeout support; `fallback_web_search` gains timeout support.
- `knowledge-rag-acquisition`: Validation threshold behavior changes for aspect-aware evidence validation scenarios.

## Impact

- **Backend code**: `backend/app/core/settings.py` (new settings), `backend/app/assistant/graph.py` (validation logic, timeouts), `backend/app/assistant/models.py` (possible helper types).
- **Tests**: `backend/tests/test_assistant_agent.py` (new regression tests for threshold behavior and timeouts).
- **Configuration**: New environment variables for strong-answer threshold, judge timeout, and web search timeout.
- **Performance**: Reduced unnecessary web search calls for strong RAG results; prevented long-running provider calls from causing timeouts.
- **No API changes**: Backend-internal behavior only; no frontend or client-facing changes.
