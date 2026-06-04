## Why

When embedded RAG evidence is insufficient, the assistant currently returns limitation text and a manual search URL even when a configured web-search provider can look up current botanical sources. This leaves users with a degraded experience and misses the opportunity to persist useful trusted fallback evidence for future answers.

## What Changes

- Add an assistant graph fallback that runs trusted web search after insufficient RAG retrieval before returning limitation-only responses.
- Generate botanical answers from trusted web-search snippets when RAG chunks are unavailable, clearly labeling them as live web evidence rather than reviewed persisted knowledge.
- Add web-search result sources to assistant response metadata.
- Persist and embed fallback web evidence through the existing knowledge ingestion/indexing path on a best-effort basis.
- Preserve the existing degraded limitation/manual-search response when web search fails or returns no usable results.
- Add tests for degraded RAG fallback search, web-evidence answers, empty/failed fallback behavior, and best-effort persistence/embedding.

## Capabilities

### New Capabilities

### Modified Capabilities

- `assistant-agent`: Insufficient botanical RAG evidence now routes through trusted web search before clarification/limitation handling, and assistant answers can cite live web evidence when no RAG chunks are available.
- `knowledge-rag-acquisition`: Trusted fallback web evidence surfaced by the assistant is persisted, chunked, embedded and indexed on a best-effort basis through the existing knowledge ingestion path.

## Impact

- Affects backend assistant orchestration in `backend/app/assistant/graph.py` and assistant tools in `backend/app/assistant/tools.py`.
- Reuses the configured search provider, including `SEARCH_PROVIDER=openai` and existing OpenAI credentials/model settings.
- Reuses existing knowledge schemas and `KnowledgeVectorIndex.ingest_document(...)` for persistence and embeddings.
- Adds/updates backend assistant tests, with possible small fake-tool extensions for web search and ingestion assertions.
