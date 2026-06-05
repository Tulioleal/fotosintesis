## Context

Assistant chat persistence and best-effort knowledge ingestion currently share the same request-scoped database session. When RAG ingestion or embedding persistence triggers a database error, PostgreSQL marks the transaction as aborted. Several ingestion paths intentionally catch those errors and convert them into tool failure metadata or degraded acquisition results, but they do not roll back the failed transaction before the session is reused.

The visible failure then appears later when saving the assistant message, even though the original fault occurred during knowledge embedding persistence or pgvector indexing. A likely trigger is an embedding dimension mismatch against the `vector(8)` pgvector column. That mismatch should be rejected in Python before SQL execution so the database transaction is not poisoned by a preventable pgvector error.

## Goals / Non-Goals

**Goals:**

- Keep assistant chat persistence usable after best-effort ingestion, embedding or vector-index failures.
- Roll back failed knowledge-ingestion transactions before returning non-blocking tool failures or degraded results.
- Validate embedding dimensions before database insert/index work can abort a transaction.
- Validate OpenAI embedding response dimensions before provider results reach RAG persistence.
- Add regression tests that reproduce the transaction-abort class of failure and prove assistant response persistence still succeeds.

**Non-Goals:**

- Change the pgvector column dimension or add a migration.
- Make best-effort fallback ingestion mandatory for assistant answers.
- Replace the request/session lifecycle or split all assistant tools into separate sessions.
- Change public assistant API response shapes.

## Decisions

- Roll back at catch boundaries that intentionally swallow ingestion failures. `AssistantTools._ingest_structured_evidence`, `AssistantTools.ingest_web_evidence`, and degraded acquisition handling should roll back the knowledge repository session before returning tool failure metadata. Alternative considered: allow the exception to bubble to the outer service layer; this would preserve transaction safety but would block fallback answers and contradict existing non-blocking tool failure requirements.
- Validate dimensions before `KnowledgeRepository.add_embeddings` executes SQL. This catches incompatible vectors before `_vector_literal` is inserted into a `vector(8)` column, preventing PostgreSQL from aborting the transaction. Alternative considered: rely on pgvector errors; that is the current failure mode and leaves the session unusable without explicit rollback.
- Use configured embedding dimension as the repository validation source. The repository should compare each embedding length to backend settings so the Python validation matches the pgvector table configuration used by current migrations and deployment env. Alternative considered: infer the allowed dimension from the first vector; this would not protect the fixed pgvector column.
- Validate OpenAI response dimensions in `OpenAIEmbeddingProvider` when `embedding_dimension` is configured. This produces a provider-specific error before a wrong-sized vector reaches RAG persistence. Alternative considered: validate only in the repository; that protects the database but delays diagnosis and loses provider-specific context.
- Keep successful ingestion commit behavior unchanged. The existing repository commits successful document/embedding writes; this change only adds validation and rollback for failure paths.

## Risks / Trade-offs

- Rolling back a shared session can also discard other uncommitted work in the same transaction. Mitigation: only call rollback at boundaries after an operation failed and the code is about to continue with a non-blocking response; earlier assistant/user-message saves already commit through repository methods.
- Repository validation depends on settings matching the actual deployed pgvector schema. Mitigation: current settings and migration default to dimension 8; deployments must continue keeping `EMBEDDING_DIMENSION` aligned with the table.
- Some tests may need to simulate PostgreSQL transaction-abort behavior without a real pgvector failure. Mitigation: use a failing repository/session or wrong-sized embedding path to assert rollback calls and subsequent assistant message persistence behavior.
