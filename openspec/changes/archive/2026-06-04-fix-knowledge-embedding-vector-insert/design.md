## Context

The knowledge ingestion path persists documents, chunks and embeddings into PostgreSQL with pgvector. Migration `0004_knowledge_rag_acquisition.py` changed `knowledge_embeddings.embedding_vector` to `vector(8)`, but the SQLAlchemy table definition still declares the same column as text. As a result, inserts bind the embedding literal as `VARCHAR`, and PostgreSQL rejects the write even when embedding generation succeeds.

The same acquisition path uses OpenAI JSON object formatting for structured knowledge generation. OpenAI requires the input messages to contain the word `json` when JSON object formatting is requested, so the prompt must make that contract explicit. Fallback acquisition is best effort, so failures in this path must not leave the database session in an aborted transaction that later prevents chat message persistence.

## Goals / Non-Goals

**Goals:**

- Make `knowledge_embeddings.embedding_vector` writes compatible with the existing `vector(8)` database column.
- Keep embedding dimension validation before insert.
- Make structured acquisition prompts comply with OpenAI JSON object response-format requirements.
- Roll back failed best-effort acquisition transactions before continuing assistant/chat persistence.
- Add focused regression tests for the observed failures.

**Non-Goals:**

- Change the configured embedding dimension or regenerate existing embeddings.
- Add a new database migration for `knowledge_embeddings.embedding_vector`.
- Replace the LlamaIndex retrieval architecture or trusted-source policy.
- Change user-facing answer content except where needed to preserve existing non-blocking fallback behavior.

## Decisions

- Use a pgvector-aware SQLAlchemy type for `embedding_vector` when available in the backend dependencies. This keeps ORM/table metadata aligned with the database and lets SQLAlchemy bind values as vector-compatible data instead of `VARCHAR`. The fallback alternative, manually appending `::vector` to text literals in repository inserts, is more brittle because it keeps the schema declaration wrong and spreads database-specific casts into write logic.
- Keep `_vector_literal()` only if the chosen vector type requires a string literal input; otherwise pass the validated list of floats directly. The implementation should prefer the representation expected by the pgvector SQLAlchemy type and avoid double-casting.
- Update the acquisition generation prompt to explicitly request a JSON document. This is the smallest provider-compatible change because the provider wrapper already requests `text.format.type=json_object`.
- Treat failed fallback ingestion as a transaction boundary. Catch paths that intentionally continue after ingestion failure must call rollback on the active session before saving chat state or returning through code that performs additional database work.

## Risks / Trade-offs

- pgvector SQLAlchemy type availability differs by package/version -> Verify the current dependency set and add the narrowest import required by the project instead of introducing a second vector library unnecessarily.
- Binding representation can differ between pgvector adapters -> Add a repository-level test that fails if the generated insert binds `embedding_vector` as `VARCHAR` or if a real pgvector-backed insert rejects the value.
- Rollback can discard unrelated uncommitted work in the same session -> Apply rollback only inside failure paths that already treat acquisition persistence as failed/best effort, before subsequent chat persistence starts.
- Prompt wording changes could affect generated document shape -> Preserve the existing structure request and add only an explicit JSON instruction, then test that the prompt passed to `generate_json` contains `json`.
