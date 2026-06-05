## Why

Assistant chat can fail after a non-blocking RAG ingestion error because the database transaction remains aborted and the same SQLAlchemy session is later reused to save the assistant message. Embedding dimension mismatches should be caught before pgvector rejects an insert, and any swallowed ingestion failure must leave the session usable for the rest of the request.

## What Changes

- Validate embedding vector dimensions before inserting knowledge embeddings into PostgreSQL/pgvector.
- Validate OpenAI embedding response dimensions against the configured embedding dimension before returning provider results.
- Roll back the active database transaction when ingestion/acquisition failures are caught and converted into non-blocking tool failures or degraded results.
- Add tests proving failed embedding ingestion does not poison the session and the assistant response can still be persisted.
- Add tests proving wrong-sized OpenAI embeddings are rejected before database writes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Assistant tool failures from RAG ingestion must not leave the chat persistence transaction unusable.
- `knowledge-rag-acquisition`: Best-effort ingestion failures must roll back failed database work before returning degraded/fallback results.
- `llamaindex-orchestration`: Embedding persistence must validate vector dimensions before pgvector writes, and provider embedding results must match configured dimensions.

## Impact

- Affected backend code: `backend/app/assistant/service.py`, `backend/app/assistant/tools.py`, `backend/app/knowledge/acquisition.py`, `backend/app/knowledge/repository.py`, `backend/app/providers/openai.py`.
- Affected tests: assistant chat/tool failure tests, knowledge RAG repository/acquisition tests, OpenAI provider tests.
- Affected systems: assistant chat persistence, SQLAlchemy transaction handling, OpenAI embedding response validation, PostgreSQL pgvector ingestion.
- No user-facing API contract changes are expected; behavior improves by preserving assistant responses when best-effort ingestion fails.
