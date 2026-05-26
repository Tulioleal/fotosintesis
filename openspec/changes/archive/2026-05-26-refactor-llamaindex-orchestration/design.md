## Context

The current knowledge acquisition flow already uses LlamaIndex for pgvector indexing and retrieval, but it still builds chunks in `app.knowledge.chunking` and creates embeddings directly through the provider registry before handing both to the vector index. This conflicts with the existing design decision that LlamaIndex should handle chunking and embedding orchestration over pgvector.

The refactor should preserve the relational persistence boundary: application tables remain the canonical store for documents, sources, chunks and embedding records. LlamaIndex becomes the orchestration path that produces chunks/nodes, obtains embeddings and indexes those nodes into pgvector.

## Goals / Non-Goals

**Goals:**

- Route successful acquisition through a LlamaIndex ingestion/indexing orchestration path for chunking and embeddings.
- Preserve required chunk metadata: `species_id`, `scientific_name`, `topic`, `source_domain`, `source_url`, `confidence`, `review_status`, `retrieved_at` and `created_at`.
- Persist the chunks and embedding records produced by the LlamaIndex orchestration path in the existing relational tables.
- Preserve existing retrieval filters, trusted-source validation, re-retrieval and degraded response behavior.
- Add regression tests that prove successful acquisition does not use app-owned custom chunking plus direct provider embedding orchestration.

**Non-Goals:**

- No changes to end-user assistant or profile UI.
- No editorial review workflow beyond existing review status fields.
- No replacement of PostgreSQL + pgvector as the canonical vector store.
- No public API contract changes unless existing tests expose an unavoidable internal interface adjustment.

## Decisions

- Introduce a LlamaIndex ingestion orchestration boundary in `KnowledgeVectorIndex` or a nearby RAG service.
  - Rationale: Acquisition should call one ingestion boundary that owns chunk/node generation, embedding orchestration and pgvector indexing.
  - Alternative considered: keep custom chunking and update the old design document. Rejected because the requested change is to make implementation match the LlamaIndex ownership decision.

- Keep relational persistence in `KnowledgeRepository` but persist LlamaIndex-produced artifacts.
  - Rationale: Existing tables and tests depend on relational records for documents, sources, chunks and embedding metadata, while LlamaIndex owns the ingestion mechanics.
  - Alternative considered: rely only on the LlamaIndex vector table for chunks and embeddings. Rejected because the knowledge persistence requirement needs traceable relational records.

- Keep metadata construction centralized and deterministic.
  - Rationale: Retrieval filters depend on stable metadata keys and values across relational rows and LlamaIndex nodes.
  - Alternative considered: let metadata be inferred from unstructured document text. Rejected because source, provenance and review fields are normative requirements.

- Degrade acquisition if LlamaIndex ingestion fails after preserving any existing retrieved evidence.
  - Rationale: The acquisition degradation requirement says trusted acquisition failures must not completely block the user experience.
  - Alternative considered: persist partial relational rows before LlamaIndex succeeds. Rejected unless implemented transactionally because it can create non-retrievable knowledge.

## Risks / Trade-offs

- LlamaIndex ingestion APIs may differ across versions -> isolate direct imports behind the existing RAG runtime and keep tests injectable with fakes.
- Persisting LlamaIndex-generated chunks may require adapting node IDs and metadata -> validate stable chunk IDs and metadata in tests.
- Embedding persistence can drift from pgvector indexing if one succeeds and the other fails -> make successful acquisition transactional or return a degraded result without claiming acquired knowledge.
- Refactoring can reduce existing test determinism -> keep fake runtime/provider hooks for unit tests while preserving production LlamaIndex ownership.
