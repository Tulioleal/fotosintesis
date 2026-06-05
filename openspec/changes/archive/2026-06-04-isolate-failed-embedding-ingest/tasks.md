## 1. Dimension Validation

- [x] 1.1 Inspect `KnowledgeRepository.add_embeddings`, OpenAI embedding provider tests and settings usage to choose the smallest dimension-validation integration point.
- [x] 1.2 Update `KnowledgeRepository.add_embeddings` to validate every embedding length against `settings.embedding_dimension` before executing insert statements.
- [x] 1.3 Update `OpenAIEmbeddingProvider.create_embeddings` to reject response vectors whose length differs from configured `embedding_dimension`.
- [x] 1.4 Ensure valid 8-dimensional embeddings still persist through the existing repository path.

## 2. Transaction Rollback on Swallowed Ingestion Failures

- [x] 2.1 Add a rollback helper or direct rollback calls for the knowledge repository session used by assistant tools.
- [x] 2.2 Roll back before returning `plant_data_lookup ingestion failed` from `AssistantTools._ingest_structured_evidence`.
- [x] 2.3 Roll back before returning `ingest_web_evidence failed` from `AssistantTools.ingest_web_evidence` when ingestion or persistence raises.
- [x] 2.4 Roll back before `KnowledgeAcquisitionService.retrieve_or_acquire` returns degraded results from caught acquisition/ingestion failures.
- [x] 2.5 Preserve successful ingestion commit behavior and existing degraded/fallback response shapes.

## 3. Regression Tests

- [x] 3.1 Add repository coverage proving a wrong-sized embedding raises a clear application error before any embedding insert is executed.
- [x] 3.2 Add OpenAI provider coverage proving wrong-sized response vectors raise `OpenAIProviderError` when `embedding_dimension` is configured.
- [x] 3.3 Add assistant tool coverage proving structured evidence ingestion failure rolls back the knowledge session and returns a non-blocking ingestion error.
- [x] 3.4 Add assistant tool or service coverage proving web evidence ingestion failure rolls back before the assistant response can be saved.
- [x] 3.5 Add acquisition coverage proving degraded acquisition after ingestion failure rolls back the failed transaction.

## 4. Verification

- [x] 4.1 Run targeted backend tests for provider, knowledge RAG/acquisition and assistant tool/service behavior.
- [x] 4.2 Run the full backend test suite or document any skipped tests and reasons.
- [x] 4.3 Run OpenSpec status/apply instructions for `isolate-failed-embedding-ingest` and confirm all implementation tasks are complete.
