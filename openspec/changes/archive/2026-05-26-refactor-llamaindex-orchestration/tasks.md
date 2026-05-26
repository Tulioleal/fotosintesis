## 1. LlamaIndex Ingestion Orchestration

- [x] 1.1 Add an ingestion orchestration method to the knowledge vector/RAG service that uses LlamaIndex to chunk trusted document content, create embeddings and index nodes in pgvector
- [x] 1.2 Ensure orchestrated nodes include stable chunk IDs and required metadata for species, scientific name, topic, source domain, source URL, confidence, review status, retrieved date and created date
- [x] 1.3 Refactor acquisition so successful trusted ingestion calls the LlamaIndex orchestration boundary instead of app-owned custom chunking plus direct provider embedding orchestration

## 2. Persistence And Failure Handling

- [x] 2.1 Persist relational document, source, chunk and embedding records from the LlamaIndex-orchestrated artifacts
- [x] 2.2 Preserve post-ingestion re-retrieval using the newly indexed evidence
- [x] 2.3 Preserve degraded acquisition responses when LlamaIndex chunking, embedding or indexing fails

## 3. Tests And Cleanup

- [x] 3.1 Update knowledge RAG tests to verify successful acquisition uses LlamaIndex ingestion orchestration
- [x] 3.2 Add regression coverage that fails if successful acquisition falls back to the custom chunking plus direct provider embedding orchestration path
- [x] 3.3 Remove or narrow obsolete custom chunking/provider embedding code paths that are no longer used by successful acquisition
- [x] 3.4 Run the focused backend knowledge RAG test suite
