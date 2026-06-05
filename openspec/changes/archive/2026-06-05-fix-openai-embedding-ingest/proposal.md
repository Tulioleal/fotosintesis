## Why

RAG ingestion fails before pgvector indexing when `EMBEDDING_PROVIDER=openai` because LlamaIndex node metadata is forwarded as an unsupported `metadata` keyword to `AsyncEmbeddings.create()`. The same path also risks vector dimension mismatches because the database and environment are configured for `vector(8)` while OpenAI embedding models return larger vectors unless `dimensions` is explicitly supplied.

## What Changes

- Filter app/LlamaIndex-only embedding metadata before calling the OpenAI embeddings SDK.
- Ensure OpenAI embedding requests use the configured embedding dimension when the selected model supports dimension shortening.
- Add regression tests covering ignored `metadata` kwargs and forwarded `dimensions` values.
- Preserve existing mock embedding provider behavior and RAG ingestion metadata persistence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llamaindex-orchestration`: Embedding creation during LlamaIndex ingestion must pass only provider-supported OpenAI embedding parameters and produce vectors aligned with configured pgvector dimensions.

## Impact

- Affected backend code: `backend/app/providers/openai.py`, RAG/LlamaIndex ingestion call sites if dimension configuration is not already centralized, and provider tests.
- Affected systems: OpenAI embeddings API usage, LlamaIndex ingestion pipeline, PostgreSQL pgvector persistence.
- No external API or user-facing breaking changes are expected.
