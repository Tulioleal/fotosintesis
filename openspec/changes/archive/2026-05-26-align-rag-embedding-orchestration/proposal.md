## Why

The RAG ingestion implementation currently calls the application embedding provider directly after LlamaIndex chunking, even though the orchestration contract says LlamaIndex handles embedding creation. Aligning the implementation with that contract removes a split ingestion path and makes embedding behavior easier to reason about and test.

## What Changes

- Move embedding creation for trusted knowledge ingestion into the LlamaIndex ingestion pipeline.
- Keep app-owned persistence of documents, chunks, embeddings and provenance metadata unchanged.
- Preserve existing degraded behavior when LlamaIndex ingestion, embedding or indexing fails.
- Update tests so successful ingestion proves embeddings are produced through LlamaIndex orchestration instead of a direct post-pipeline provider call.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `llamaindex-orchestration`: Clarify and enforce that successful acquisition ingestion uses a LlamaIndex pipeline transformation for embedding creation rather than a direct app embedding-provider call after chunking.

## Impact

- Affected code: `backend/app/knowledge/rag.py` ingestion orchestration.
- Affected tests: backend knowledge/RAG tests that cover ingestion orchestration and embedding calls.
- APIs: No public API changes.
- Dependencies: No new external dependency is expected; use the existing LlamaIndex integration surface.
