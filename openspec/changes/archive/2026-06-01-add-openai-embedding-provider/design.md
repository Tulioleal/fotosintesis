## Context

The backend already exposes an `EmbeddingProvider` interface and routes RAG ingestion, knowledge acquisition and assistant embedding tools through `providers.embeddings`. The provider registry supports independent model, vision, judge, search and embedding roles, but `_build_embedding_provider()` currently returns only `MockEmbeddingProvider` and rejects `EMBEDDING_PROVIDER=openai`.

OpenAI-backed model, vision and judge providers live in `app.providers.openai` and are constructed by `app.providers.factory` with role-specific model settings and `OPENAI_API_KEY` validation. The embedding implementation should follow that pattern so domain code continues to depend only on internal interfaces and provider result DTOs.

## Goals / Non-Goals

**Goals:**

- Support `EMBEDDING_PROVIDER=openai` as an independently selectable embedding role.
- Add `OPENAI_EMBEDDING_MODEL` configuration and document it wherever provider environment settings are documented.
- Implement OpenAI embeddings behind `EmbeddingProvider.create_embeddings()` and return existing `EmbeddingResult` objects.
- Reuse existing provider-call logging with role `embeddings` and operation `create_embeddings`.
- Preserve mock embeddings as the default and keep unselected OpenAI roles from requiring credentials.
- Keep RAG ingestion, knowledge acquisition, assistant embedding tools and `/health` reporting on the existing provider registry path.

**Non-Goals:**

- Change the RAG ingestion, retrieval or trusted acquisition algorithms.
- Replace the pgvector table or automatically migrate existing vectors.
- Add a real search provider or couple embeddings to search provider selection.
- Add frontend controls for provider configuration.
- Store provider settings in the database.

## Decisions

1. Add a dedicated `OpenAIEmbeddingProvider` in `app.providers.openai`.

   The class will implement `EmbeddingProvider.create_embeddings(texts, **kwargs)` and use the existing OpenAI client helper. This keeps SDK usage isolated with the existing OpenAI provider classes instead of spreading OpenAI calls into RAG or acquisition code.

   Alternative considered: use a LlamaIndex OpenAI embedding adapter directly in the RAG pipeline. That would bypass the internal provider interface and leave assistant embedding tools and acquisition query embeddings on a separate path.

2. Use `OPENAI_EMBEDDING_MODEL` instead of reusing text, vision or judge model settings.

   Embedding models have different capabilities, dimensions and pricing from generation models. A dedicated setting keeps the role independent and mirrors the existing role-specific model-name pattern.

   Alternative considered: reuse `OPENAI_TEXT_MODEL`. This would reduce configuration but make invalid model selection easier and couple embedding behavior to generation configuration.

3. Keep credential validation role-specific.

   `_build_embedding_provider()` will receive settings and require `OPENAI_API_KEY` only when the embedding provider is `openai`. Selecting OpenAI embeddings must not require OpenAI model, vision or judge roles, and selecting those roles must not switch embeddings implicitly.

   Alternative considered: validate OpenAI credentials globally when any OpenAI setting is present. This would break local and CI workflows that intentionally keep most roles mocked.

4. Map SDK responses into `EmbeddingResult` at the provider boundary.

   The provider will extract embedding vectors from the OpenAI response, preserve input ordering, and return provider name, configured model and sanitized metadata. It should fail clearly if the response count does not match the requested text count.

   Alternative considered: return the raw OpenAI response and let callers extract vectors. This would leak SDK details into domain services and make testing harder.

5. Treat vector dimension alignment as explicit configuration, not automatic migration.

   Existing `embedding_dimension` drives pgvector store creation and defaults to the mock dimension. OpenAI embedding rollout requires operators to configure a dimension compatible with the selected OpenAI embedding model and any existing vector table state.

   Alternative considered: infer and overwrite `embedding_dimension` from the selected model. That could silently conflict with existing tables and obscure migration decisions.

## Risks / Trade-offs

- Vector dimension mismatch -> Document that `EMBEDDING_DIMENSION` must match the selected OpenAI embedding model and existing pgvector table; tests should cover provider response mapping but not destructive vector migrations.
- OpenAI SDK response shape changes -> Isolate parsing in `OpenAIEmbeddingProvider` and cover it with mocked SDK response tests.
- Unexpected cost or latency -> Preserve mocks by default and emit provider-call logs, metrics and traces for embedding calls.
- Empty or malformed embedding responses -> Validate response counts and vector shapes before returning `EmbeddingResult`.
- Configuration sprawl -> Keep setting names role-oriented and update all existing provider env examples consistently.

## Migration Plan

1. Deploy code with mocks still configured by default.
2. Configure `OPENAI_API_KEY`, `EMBEDDING_PROVIDER=openai`, `OPENAI_EMBEDDING_MODEL` and a matching embedding dimension in the target environment.
3. Rebuild or migrate vector data only when changing dimensions from the mock/default embedding size to the OpenAI model dimension.
4. Roll back by setting `EMBEDDING_PROVIDER=mock` and restoring the previous vector dimension/table configuration if needed.

## Open Questions

- Which OpenAI embedding model and dimension should be the documented production recommendation?
- Should this change add an explicit `EMBEDDING_DIMENSION` environment example if it is currently only a settings field default?
