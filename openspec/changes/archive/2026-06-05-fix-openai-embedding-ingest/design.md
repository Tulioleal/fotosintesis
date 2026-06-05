## Context

Trusted knowledge ingestion uses LlamaIndex orchestration to chunk, embed and index knowledge nodes into PostgreSQL pgvector. During that flow, node metadata is useful for persistence and retrieval filtering, but it is not a valid parameter for the OpenAI embeddings SDK. The current OpenAI provider forwards arbitrary keyword arguments to `AsyncEmbeddings.create()`, so LlamaIndex metadata causes ingestion to fail before pgvector indexing.

The backend also configures a fixed embedding vector size through `EMBEDDING_DIMENSION` and the database migration defines `embedding_vector` as `vector(8)`. OpenAI `text-embedding-3-*` models support the `dimensions` parameter, but without forwarding that configured value the API returns the model default dimension, which can fail persistence against the fixed pgvector column.

## Goals / Non-Goals

**Goals:**

- Keep LlamaIndex metadata available for app persistence and retrieval while preventing it from being sent to the OpenAI embeddings SDK.
- Ensure OpenAI embedding vectors match the configured backend embedding dimension when using a dimension-configurable embedding model.
- Add targeted regression coverage around provider argument handling.
- Preserve existing mock provider behavior and public provider interfaces.

**Non-Goals:**

- Change the pgvector schema or migration dimension in this change.
- Replace LlamaIndex orchestration or alter trusted-source validation.
- Add a new embedding provider abstraction.

## Decisions

- Sanitize OpenAI embedding kwargs at the provider boundary. This keeps caller code simple, protects all current and future OpenAI embedding call sites from unsupported internal kwargs, and avoids spreading SDK-specific filtering across RAG/LlamaIndex code. Alternative considered: stop passing metadata from `rag.py`; this is narrower but leaves the provider vulnerable to the same issue from another call site.
- Forward `dimensions` from configured embedding dimension for OpenAI embeddings. The provider should supply the backend's configured dimension when creating embeddings so OpenAI returns vectors compatible with the existing pgvector column. Alternative considered: change `EMBEDDING_DIMENSION` and the migration to OpenAI's default model size; this is larger, requires data/schema migration work, and is unnecessary while the selected OpenAI model supports shortened embeddings.
- Keep metadata out of OpenAI API calls but not out of ingestion artifacts. Metadata remains attached to nodes and persisted by app/LlamaIndex code; only the SDK request parameters are filtered.
- Test at the provider boundary with a mocked OpenAI embeddings client. This verifies the exact SDK call arguments without requiring network access.

## Risks / Trade-offs

- Unsupported future kwargs could still reach the SDK if only `metadata` is filtered. Mitigation: restrict forwarding to a small allowlist of OpenAI embeddings parameters or explicitly drop known app-only kwargs before the SDK call.
- Some OpenAI embedding models may not support shortened dimensions. Mitigation: only configure/use dimension forwarding for `text-embedding-3-*` models or fail with a clear provider error if the configured model rejects `dimensions`.
- Existing persisted embeddings may have a different dimension in non-local environments. Mitigation: this change does not alter schema; deployments should keep `EMBEDDING_DIMENSION`, migrations and provider configuration aligned before ingestion resumes.
