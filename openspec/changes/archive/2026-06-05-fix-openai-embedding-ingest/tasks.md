## 1. Provider Argument Handling

- [x] 1.1 Inspect `backend/app/providers/openai.py` embedding provider construction and `create_embeddings` call sites to confirm where embedding dimension configuration is available.
- [x] 1.2 Update `OpenAIEmbeddingProvider.create_embeddings` to remove app-only `metadata` from kwargs before calling `self._client.embeddings.create`.
- [x] 1.3 Forward the configured embedding dimension as `dimensions` for OpenAI embedding requests when the caller has not already supplied `dimensions`.
- [x] 1.4 Keep mock embedding provider behavior unchanged so tests and local ingestion can still pass metadata kwargs.

## 2. RAG Ingestion Compatibility

- [x] 2.1 Verify the LlamaIndex ingestion path in `backend/app/knowledge/rag.py` can continue passing metadata for app persistence without requiring call-site filtering.
- [x] 2.2 Confirm the configured OpenAI embedding vector length matches the pgvector column dimension used by current migrations and `EMBEDDING_DIMENSION`.

## 3. Regression Tests

- [x] 3.1 Add a provider test that calls OpenAI embedding creation with `metadata` and verifies the mocked SDK receives no `metadata` argument.
- [x] 3.2 Add a provider test that verifies OpenAI embedding creation forwards the configured `dimensions` value when using the OpenAI provider.
- [x] 3.3 Add or update an ingestion-facing test to ensure metadata remains available to the RAG/LlamaIndex persistence path after provider-level filtering.

## 4. Verification

- [x] 4.1 Run the targeted backend provider and RAG tests.
- [x] 4.2 Run the relevant backend test suite or document any skipped tests and reasons.
- [x] 4.3 Run OpenSpec validation/status for `fix-openai-embedding-ingest` and confirm the change remains apply-ready.
