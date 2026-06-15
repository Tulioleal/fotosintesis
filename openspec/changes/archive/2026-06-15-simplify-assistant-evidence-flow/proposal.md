## Why

The assistant plant-care answer path currently performs too many fallback and persistence steps before returning a user-facing response, which increases latency and makes evidence state difficult to explain. This change simplifies the flow around explicit evidence status so the assistant can answer transparently from RAG and live web evidence without blocking on structured API lookup or synchronous embedding persistence.

## What Changes

- Replace the chat-time fallback chain with an evidence-first pipeline: classifier, user context, enriched RAG retrieval, RAG answerability judge, web search when RAG is not full, one final combined judge, answer synthesis, and post-response ingestion scheduling.
- Extend answerability from a boolean-only result to explicit `full`, `partial`, `insufficient`, and `contradictory` statuses while keeping compatibility with the existing `answerable` field.
- Improve RAG retrieval query construction by including confirmed taxonomy, topic, required aspects, and the original user question.
- Remove Trefle/Perenual structured plant-data lookup from the normal chat-time plant-care answer path while keeping the providers available elsewhere.
- Replace per-source web answerability judging and deterministic keyword rejection with one final combined semantic judge plus structural validation of judge output.
- Allow partial, insufficient, and contradictory answers to include conservative general guidance only when clearly labeled as not source-validated for the specific plant/question.
- Schedule background ingestion after the assistant response is prepared, using a dedicated database session and explicit error logging.
- Persist only small validated source-supported claim documents derived from final judge `source_support`; do not persist final assistant answer text, full pages by default, contradictory evidence, insufficient evidence, or general LLM guidance.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Change plant-care orchestration, answerability routing, answer synthesis policy, source transparency, chat-time structured lookup usage, and post-response ingestion scheduling.
- `knowledge-rag-acquisition`: Change retrieval query construction, web fallback evaluation, validated web-claim persistence, and ingestion timing for assistant fallback evidence.
- `structured-plant-data-lookup`: Clarify that Trefle/Perenual lookup remains available as backend capability but is not used in the normal assistant chat-time plant-care answer path for this flow.

## Impact

- Affected backend areas include assistant graph routing, assistant service response handling, assistant tools, care contracts, knowledge acquisition, RAG retrieval, database session access, and tests for assistant and RAG behavior.
- The assistant response metadata will carry richer evidence status, coverage, missing aspects, source support, contradictions, and web-search path diagnostics.
- No database migration or full queue system is required; existing metadata JSON is used for validated claim metadata.
- Existing emergency model-failure fallback remains as last-resort technical protection.
