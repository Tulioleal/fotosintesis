## 1. Configuration

- [x] 1.1 Add `openai_embedding_model` to backend settings with a safe documented default.
- [x] 1.2 Document `OPENAI_EMBEDDING_MODEL` in `backend/.env.example`, Kubernetes values examples and deployment docs.
- [x] 1.3 Document embedding dimension alignment expectations for OpenAI embedding rollout.

## 2. Provider Implementation

- [x] 2.1 Add `OpenAIEmbeddingProvider` to `app.providers.openai` implementing `EmbeddingProvider.create_embeddings()`.
- [x] 2.2 Map OpenAI embedding API responses into existing `EmbeddingResult` objects while preserving input order.
- [x] 2.3 Validate malformed or count-mismatched OpenAI embedding responses with clear provider errors.
- [x] 2.4 Wrap OpenAI embedding SDK calls with provider-call logging using provider `openai-embedding`, role `embeddings` and operation `create_embeddings`.

## 3. Provider Registry Wiring

- [x] 3.1 Update provider factory imports and `_build_embedding_provider()` to receive settings.
- [x] 3.2 Support `EMBEDDING_PROVIDER=openai` with role-specific `OPENAI_API_KEY` validation and `OPENAI_EMBEDDING_MODEL` selection.
- [x] 3.3 Preserve mock embeddings as the default and keep all provider roles independently selectable.
- [x] 3.4 Confirm `/health` reports `OpenAIEmbeddingProvider` when OpenAI embeddings are selected.

## 4. Tests

- [x] 4.1 Add tests proving OpenAI embeddings can be selected independently from model, vision, judge and search providers.
- [x] 4.2 Add tests proving missing OpenAI credentials fail only when embeddings are selected as OpenAI.
- [x] 4.3 Add tests for OpenAI embedding response mapping into `EmbeddingResult`.
- [x] 4.4 Add tests for malformed or count-mismatched OpenAI embedding responses.
- [x] 4.5 Add tests or assertions covering provider-call logging metadata sanitization for OpenAI embedding calls.
- [x] 4.6 Confirm default local and CI provider configuration still uses deterministic mock embeddings without OpenAI credentials.

## 5. Verification

- [x] 5.1 Run the backend provider and RAG test suites affected by embedding provider wiring.
- [x] 5.2 Run formatting and linting checks for changed backend files.
- [x] 5.3 Verify OpenSpec status reports this change ready for implementation.
