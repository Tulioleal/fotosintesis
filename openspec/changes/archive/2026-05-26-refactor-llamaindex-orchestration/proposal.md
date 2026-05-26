## Why

The knowledge RAG acquisition implementation currently diverges from its design contract: LlamaIndex is intended to orchestrate chunking, embedding and pgvector indexing, but the code uses custom chunking plus direct provider embedding calls. Aligning the implementation now prevents the evidence layer from growing around two competing ingestion paths.

## What Changes

- Refactor knowledge ingestion so LlamaIndex orchestrates text chunking and embedding creation before pgvector indexing.
- Keep application persistence as the canonical relational record for documents, sources, chunks and embeddings.
- Preserve the existing retrieval, trusted-source acquisition and degradation behavior.
- Update tests to fail if acquisition bypasses LlamaIndex orchestration for successful ingestion.

## Capabilities

### New Capabilities

- `llamaindex-orchestration`: LlamaIndex-owned chunking and embedding orchestration for acquired knowledge before pgvector retrieval.

### Modified Capabilities

- None.

## Impact

- Affects backend knowledge acquisition, chunk/index services, persistence boundaries and RAG tests.
- May adjust how chunk metadata and embedding records are produced, while preserving the existing external service behavior.
