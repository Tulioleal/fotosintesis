## Context

The active knowledge RAG acquisition implementation persists relational knowledge records and stores embeddings, but runtime retrieval still calls `KnowledgeRepository.retrieve_chunks`, which uses SQLAlchemy plus Python cosine scoring. The spec and design for `knowledge-rag-acquisition` require LlamaIndex with PostgreSQL + pgvector retrieval, and current LlamaIndex code is only an unused adapter.

Current LlamaIndex Python docs show `PGVectorStore.from_params(...)`, `VectorStoreIndex.from_vector_store(...)`, and retrievers/query engines backed by metadata filters. The backend must add the PostgreSQL vector store package and make this path the normal retrieval path used by acquisition.

## Goals / Non-Goals

**Goals:**

- Make runtime retrieval use LlamaIndex `PGVectorStore` + `VectorStoreIndex` over PostgreSQL pgvector.
- Keep relational knowledge document, source and chunk persistence as the source of provenance and audit metadata.
- Store vector nodes with metadata sufficient for species, topic, source, confidence, review status and date filtering.
- Keep acquisition degradation behavior when trusted acquisition, LlamaIndex or pgvector fails.
- Add tests that verify acquisition no longer depends on `KnowledgeRepository.retrieve_chunks` for runtime retrieval.

**Non-Goals:**

- No assistant UI or plant profile UI changes.
- No editorial review workflow beyond existing review status fields.
- No provider-specific embedding model rollout beyond declaring and wiring required dimensions/configuration.
- No broad rewrite of all knowledge persistence models unless required to align with LlamaIndex node IDs.

## Decisions

- Runtime retrieval will go through a new LlamaIndex-backed retriever service, not `KnowledgeRepository.retrieve_chunks`.
  Rationale: this directly satisfies the spec and prevents the previous SQL-only path from silently passing verification.
  Alternative considered: keep SQL retrieval and document it as intentional. That would require changing the existing requirement and design, so it is rejected for this fix.

- Relational tables will remain for documents, sources and chunks; LlamaIndex will own vector retrieval over its pgvector table.
  Rationale: relational records preserve the existing provenance model, while LlamaIndex handles vector storage/retrieval.
  Alternative considered: remove the custom embedding table and rely only on LlamaIndex storage. That is a larger migration and risks losing audit-friendly relationships.

- Chunk IDs will be mirrored into LlamaIndex node IDs or metadata so retrieved nodes can be mapped back to relational `KnowledgeChunk` responses.
  Rationale: callers already expect structured chunk records with provenance metadata.
  Alternative considered: return raw LlamaIndex nodes. That would leak implementation details and weaken consistency with existing service schemas.

- Metadata filters will be built with LlamaIndex `MetadataFilters` from the existing `KnowledgeRetrievalFilters` model.
  Rationale: this preserves current filter semantics while moving vector search execution to pgvector.
  Alternative considered: implement separate filter models for LlamaIndex. That would duplicate validation and increase drift risk.

- Required packages will be added explicitly to backend dependencies, including the PostgreSQL vector-store integration.
  Rationale: the runtime path must not depend on optional packages being installed out of band.
  Alternative considered: keep lazy imports only. That preserves import safety but fails deployability.

## Risks / Trade-offs

- LlamaIndex package versions may introduce dependency weight or transitive conflicts -> pin minimum compatible packages and keep tests focused on service boundaries.
- Local SQLite tests cannot exercise PostgreSQL pgvector directly -> add unit tests around the retriever interface and metadata mapping, and keep integration hooks isolated for PostgreSQL environments.
- Existing custom `knowledge_embeddings` data may not automatically exist in LlamaIndex's vector table -> write ingestion through LlamaIndex going forward and document any required backfill if existing deployed data exists.
- Embedding dimension mismatch can break pgvector inserts -> source the dimension from settings and align migrations/configuration before production use.
- LlamaIndex failures can affect retrieval latency or availability -> preserve degraded acquisition responses and add explicit fallback/limitation reporting.

## Migration Plan

- Add LlamaIndex dependencies to `backend/pyproject.toml`.
- Introduce a LlamaIndex knowledge retriever/indexer abstraction beside the existing repository.
- Update acquisition to call the LlamaIndex retriever before and after acquisition.
- Update ingestion to insert newly generated chunks into LlamaIndex with stable node IDs and metadata.
- Keep the existing SQL repository methods for relational persistence and non-vector inspection only.
- Add tests for dependency wiring, metadata filter mapping, LlamaIndex retriever invocation and degradation on retrieval failure.

## Open Questions

- Should already persisted local development embeddings be backfilled into the LlamaIndex vector table, or is forward-only ingestion enough before deployment?
- What production embedding dimension should replace the current mock-friendly default before pgvector migrations are run outside tests?
