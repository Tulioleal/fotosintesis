## 1. Ingestion Pipeline

- [x] 1.1 Add a minimal LlamaIndex-compatible embedding transformation/adapter that delegates to the existing `EmbeddingProvider` and records provider/model attribution.
- [x] 1.2 Update `LlamaIndexRuntime.orchestrate_ingestion` so `IngestionPipeline.transformations` includes `SentenceSplitter` followed by the embedding transformation.
- [x] 1.3 Build `KnowledgeChunk` and `OrchestratedKnowledgeIngestion` results from pipeline nodes with attached embeddings, preserving current metadata, ordering and empty-content handling.
- [x] 1.4 Remove the direct post-pipeline `embedding_provider.create_embeddings(...)` call from `orchestrate_ingestion`.

## 2. Behavior Preservation

- [x] 2.1 Preserve current validation for trusted sources and no-chunk ingestion results.
- [x] 2.2 Preserve persisted provider/model attribution for embedding records.
- [x] 2.3 Preserve acquisition degradation behavior when LlamaIndex ingestion, embedding or indexing fails.

## 3. Tests

- [x] 3.1 Add or update focused tests proving `orchestrate_ingestion` obtains embeddings from LlamaIndex pipeline-produced nodes.
- [x] 3.2 Add or update tests proving the direct post-pipeline provider embedding call is no longer used as the orchestration mechanism.
- [x] 3.3 Run the backend knowledge/RAG test suite and fix regressions.
