## Why

The knowledge RAG acquisition slice declares LlamaIndex + PostgreSQL pgvector retrieval, but runtime retrieval currently bypasses LlamaIndex and scores vectors in application code. This change closes that verification gap before the knowledge capability is archived or used by profile and assistant flows.

## What Changes

- Wire runtime knowledge retrieval through LlamaIndex `PGVectorStore` and `VectorStoreIndex` instead of direct SQLAlchemy retrieval with Python cosine sorting.
- Add the required LlamaIndex PostgreSQL vector-store dependencies to the backend package configuration.
- Store newly ingested chunks and embeddings in the LlamaIndex pgvector table while preserving relational knowledge document, source and chunk records.
- Map existing knowledge retrieval filters to LlamaIndex metadata filters for species, topic, source, confidence, review status and dates.
- Keep graceful degradation behavior when LlamaIndex, pgvector or ingestion persistence fails.
- Add regression tests that fail if acquisition retrieves through the legacy SQL-only path.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `knowledge-rag-acquisition`: Runtime retrieval must use LlamaIndex backed by PostgreSQL pgvector, not only the relational repository fallback.

## Impact

- Affects backend knowledge retrieval, ingestion, dependency configuration, tests and the active `add-knowledge-rag-acquisition` change implementation.
- Adds LlamaIndex runtime dependencies for PostgreSQL pgvector retrieval.
- May require migration or table-alignment work between existing knowledge relational tables and the LlamaIndex vector table.
