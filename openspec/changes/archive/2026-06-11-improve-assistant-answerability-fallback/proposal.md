## Why

The assistant currently treats high-confidence retrieved RAG chunks as sufficient even when those chunks do not directly answer the user's exact question. This causes answers such as "the available evidence does not say" for pet safety, edibility, native range or water-temperature questions instead of continuing to structured lookup and trusted web search.

This change makes evidence sufficiency answerability-based rather than confidence-only. The assistant should only stop at RAG or structured evidence when the configured judge provider says that evidence directly answers the current user question; otherwise it should continue through the existing fallback path and use conservative safety guidance when no direct evidence is found for safety-sensitive topics.

## What Changes

- Add a strict answerability evaluation step after RAG retrieval when chunks are available.
- Use `providers.judge.judge_response()` for answerability decisions instead of the runtime generation provider.
- Replace confidence-only sufficiency logic with judge-confirmed direct answerability for the exact user question.
- Preserve the fallback order when RAG is not answerable: structured plant-data lookup first, then trusted web search.
- Add answerability evaluation for structured plant-data evidence so generic structured metadata does not block trusted web search.
- Keep existing trusted web search behavior, including trusted-first result selection and external fallback handling from the configured search provider.
- Add conservative safety fallback behavior for pet safety, edibility, toxicity and consumption questions when all direct evidence sources are unavailable or not answerable.
- Record internal fallback reasons such as `rag_not_answerable`, `structured_not_answerable`, `web_search_used`, `web_search_no_direct_answer` and `conservative_safety_fallback` without making internal routing details prominent in the user-facing answer.
- Add structured observability for answerability decisions so runtime logs show whether the assistant used RAG only, structured lookup, trusted web search or conservative fallback.
- Add tests covering non-answerable general care chunks, directly answerable chunks, structured evidence that does not answer, web-search fallback, conservative safety fallback and internal fallback reason tracking.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Changes sufficiency evaluation, fallback routing and final fallback behavior so answers are based on evidence that directly answers the user's exact botanical question.
- `provider-observability`: Adds structured logging requirements for answerability and fallback routing decisions so operators can confirm when RAG, structured lookup, trusted web search or conservative fallback was used.

## Impact

- Assistant graph sufficiency evaluation changes from chunk-confidence thresholding to strict judge-based answerability.
- Assistant tool/fallback routing may call structured lookup and trusted web search more often for specific knowledge-gap questions.
- Judge provider usage increases because answerability checks run for retrieved RAG evidence and structured plant-data evidence.
- Assistant state or response metadata needs internal fallback reason tracking for debugging.
- Provider/search logs should include explicit answerability/fallback decision events in addition to provider call logs.
- Tests in `test_assistant_agent.py` and related assistant sufficiency/fallback tests need updates to reflect the new routing behavior.
