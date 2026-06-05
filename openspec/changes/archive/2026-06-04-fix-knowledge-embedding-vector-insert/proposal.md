## Why

Trusted knowledge ingestion currently fails when persisting embeddings because SQLAlchemy declares `embedding_vector` as text while the migrated PostgreSQL column is `vector(8)`. The same acquisition path also sends a JSON-formatted OpenAI request without explicitly mentioning JSON in the input, and ingestion failures can leave the database session unusable for the subsequent chat message save.

## What Changes

- Align the backend knowledge embedding model/write path with the real pgvector column type so inserts no longer bind `embedding_vector` as `VARCHAR`.
- Preserve existing embedding dimension validation before persistence.
- Update the structured acquisition prompt used with JSON object response formatting so it explicitly requests JSON.
- Ensure best-effort acquisition or fallback persistence failures roll back the current database transaction before chat persistence continues.
- Add regression coverage for pgvector embedding insertion, JSON prompt requirements, and non-blocking ingestion failure behavior.

## Capabilities

### New Capabilities

### Modified Capabilities

- `knowledge-rag-acquisition`: Knowledge embedding persistence and acquisition generation must use the database/provider contracts required by pgvector and OpenAI JSON object formatting.
- `assistant-agent`: Fallback acquisition/persistence failures must remain non-blocking and must not poison the chat database session.

## Impact

- Affected backend code: `backend/app/auth/tables.py`, `backend/app/knowledge/repository.py`, `backend/app/knowledge/acquisition.py`, assistant/fallback orchestration around ingestion failure handling.
- Affected database behavior: no migration is expected; this aligns SQLAlchemy with the existing `vector(8)` schema.
- Affected tests: backend unit/integration tests for knowledge ingestion, OpenAI JSON generation prompts, and assistant fallback failure handling.
