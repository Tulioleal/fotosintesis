## 1. Pgvector Persistence

- [x] 1.1 Inspect backend pgvector/vector dependencies and choose the existing SQLAlchemy vector type or minimal compatible cast approach.
- [x] 1.2 Update `knowledge_embeddings.embedding_vector` metadata so SQLAlchemy no longer binds the column as `VARCHAR` for inserts.
- [x] 1.3 Update the repository insert path to pass the embedding representation expected by the selected vector binding while preserving dimension validation.

## 2. Acquisition Provider Contract

- [x] 2.1 Update the structured knowledge acquisition prompt to explicitly request JSON while preserving the existing botanical knowledge structure.
- [x] 2.2 Add a regression test that verifies the acquisition prompt sent to `generate_json` contains `json` when JSON object formatting is used.

## 3. Failure Recovery

- [x] 3.1 Locate best-effort acquisition/fallback persistence catch paths that continue after ingestion, embedding or indexing failure.
- [x] 3.2 Add rollback handling before subsequent database writes in those continuing failure paths.
- [x] 3.3 Add regression coverage that a failed fallback ingestion records a non-blocking failure and does not prevent assistant chat response persistence.

## 4. Verification

- [x] 4.1 Add or update a repository-level test proving embedding persistence uses a pgvector-compatible value instead of `VARCHAR` and still rejects wrong dimensions.
- [x] 4.2 Run the relevant backend test suite for knowledge acquisition, repository embedding persistence and assistant fallback behavior.
- [x] 4.3 Run OpenSpec validation/status checks for `fix-knowledge-embedding-vector-insert`.
