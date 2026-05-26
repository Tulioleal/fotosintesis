## Context

The `llamaindex-orchestration` capability requires successful trusted knowledge ingestion to use LlamaIndex for chunking, embedding creation and pgvector indexing. The current `LlamaIndexRuntime.orchestrate_ingestion` builds a LlamaIndex `IngestionPipeline` for chunking only, then calls the application `EmbeddingProvider` directly to create embeddings after the pipeline has run. That creates a mismatch between the contract and the implementation, while the rest of the persistence and retrieval flow already treats the result as LlamaIndex-orchestrated.

## Goals / Non-Goals

**Goals:**

- Have the successful ingestion path create embeddings as part of the LlamaIndex ingestion pipeline.
- Preserve existing chunk metadata, embedding persistence fields, indexing behavior and degraded acquisition behavior.
- Keep the application provider implementation usable as the embedding backend, but invoke it through a LlamaIndex embedding transformation/adapter instead of a direct post-pipeline call.
- Add or update tests that fail if `orchestrate_ingestion` bypasses LlamaIndex for embedding creation.

**Non-Goals:**

- No changes to retrieval query embedding generation for acquisition lookup.
- No replacement of the configured provider abstraction or provider response schema.
- No changes to database tables, public APIs or trusted-source acquisition rules.
- No broad LlamaIndex refactor outside the ingestion orchestration path.

## Decisions

- Add a minimal LlamaIndex embedding adapter/transform used by `IngestionPipeline.transformations` after `SentenceSplitter`.
  - Rationale: This makes chunking and embedding a single LlamaIndex pipeline responsibility while keeping the existing application provider as the actual embedding backend.
  - Alternative considered: Replace the application provider with a native LlamaIndex embed model. That would increase dependency/configuration surface and risk changing provider observability semantics.
- Return embeddings from the resulting LlamaIndex nodes rather than creating them after pipeline execution.
  - Rationale: The orchestration boundary becomes clear: pipeline output nodes contain text, metadata and embeddings.
  - Alternative considered: Keep direct provider embedding after chunking and treat the design text as aspirational. That preserves the current mismatch and weakens the spec contract.
- Keep persisted provider/model values sourced from the adapter's provider result.
  - Rationale: Existing embedding records need provider/model attribution for traceability without requiring schema changes.
  - Alternative considered: Store LlamaIndex as the provider. That would hide the actual embedding backend and reduce operational usefulness.

## Risks / Trade-offs

- LlamaIndex transformation APIs may be synchronous while the provider interface is async -> Use a small adapter boundary that runs the provider safely from the async orchestration method or selects an async-compatible LlamaIndex hook if available.
- Node ordering or empty content handling could change when embeddings are attached in the pipeline -> Preserve current filtering and index assignment semantics in tests.
- Provider/model attribution could be lost if embeddings are only read from nodes -> Keep adapter state for the latest provider result and validate it before returning ingestion output.
- Existing fake runtimes may obscure the real orchestration regression -> Add focused tests around `LlamaIndexRuntime.orchestrate_ingestion` or its embedding adapter, not only acquisition service fakes.
