## Context

`knowledge_embeddings.embedding_vector` now uses the pgvector SQLAlchemy `VECTOR(8)` type, and repository inserts pass the validated list of floats directly. Existing regression coverage proves the table metadata compiles to `vector(8)` and that wrong dimensions are rejected before persistence, but it does not exercise the insert statement binding path that originally failed as `VARCHAR` against PostgreSQL.

## Goals / Non-Goals

**Goals:**

- Add a focused backend regression test that compiles the embedding insert path under the PostgreSQL dialect.
- Assert `embedding_vector` is associated with a pgvector-compatible bind/type rather than a text or `VARCHAR` binding.
- Keep the test fast and deterministic without requiring a live PostgreSQL or pgvector database.

**Non-Goals:**

- Change runtime repository behavior or database schema.
- Add a new migration or dependency.
- Replace the existing SQLite-backed repository persistence tests.

## Decisions

- Test SQLAlchemy compilation instead of requiring a live PostgreSQL container. This directly verifies the bind/type contract that caused the failure while keeping the backend test suite local and fast.
- Prefer reusing the same insert construction shape as `KnowledgeRepository.add_embeddings()` so the test covers the repository write contract instead of only inspecting table metadata. If direct async-session interception is simpler and stable, exercise `add_embeddings()` with a fake session that captures the executed insert; otherwise compile a generated `insert(knowledge_embeddings).values(...)` statement that mirrors the repository path.
- Assert against PostgreSQL dialect compilation metadata and bind parameter type for `embedding_vector`, not only rendered SQL text. Rendered SQL can vary across SQLAlchemy/pgvector versions, while the bind type is the behavior relevant to avoiding `VARCHAR`.
- Keep the existing wrong-dimension regression test unchanged because it verifies a separate validation contract.

## Risks / Trade-offs

- SQLAlchemy internals around compiled bind lookup may differ by version -> Use public compiled attributes where practical and make the assertion narrow to the `embedding_vector` parameter type.
- A pure compilation test cannot prove a live pgvector extension accepts the value -> This is acceptable because the change targets the prior bind-type regression and avoids adding infrastructure to the unit suite.
- Mirroring repository insert construction could drift if repository code changes -> Prefer capturing the statement emitted by `KnowledgeRepository.add_embeddings()` when feasible.
