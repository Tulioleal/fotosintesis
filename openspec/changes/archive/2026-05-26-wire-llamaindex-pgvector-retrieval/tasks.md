## 1. LlamaIndex Runtime Retrieval

- [x] 1.1 Add required LlamaIndex PostgreSQL vector-store dependencies to backend package configuration
- [x] 1.2 Implement a LlamaIndex-backed knowledge retriever/indexer service using `PGVectorStore` and `VectorStoreIndex`
- [x] 1.3 Map `KnowledgeRetrievalFilters` to LlamaIndex metadata filters for species, topic, source, confidence, review status and date fields
- [x] 1.4 Persist newly ingested chunks into the LlamaIndex pgvector index with stable chunk IDs and required metadata
- [x] 1.5 Update acquisition to use the LlamaIndex retriever for existing evidence checks and post-ingestion re-retrieval
- [x] 1.6 Keep relational repository methods for document, source, chunk and audit persistence without using SQL-only vector scoring as the successful runtime RAG path

## 2. Failure Handling And Verification

- [x] 2.1 Preserve degraded acquisition responses when LlamaIndex retrieval or indexing fails
- [x] 2.2 Add tests for metadata filter mapping and LlamaIndex retriever invocation during acquisition
- [x] 2.3 Add regression coverage that fails if acquisition calls `KnowledgeRepository.retrieve_chunks` as the successful runtime retrieval path
- [x] 2.4 Add dependency/import verification for the LlamaIndex PostgreSQL vector-store integration
