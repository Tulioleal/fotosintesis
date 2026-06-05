## 1. Test Design

- [x] 1.1 Inspect the current embedding repository tests and pgvector column metadata assertions to choose the narrowest test location.
- [x] 1.2 Determine whether to capture the statement emitted by `KnowledgeRepository.add_embeddings()` or compile an equivalent `insert(knowledge_embeddings)` statement that mirrors the repository path.

## 2. Regression Coverage

- [x] 2.1 Add a focused PostgreSQL dialect compilation test that verifies the `embedding_vector` bind uses the pgvector SQLAlchemy type rather than text or `VARCHAR`.
- [x] 2.2 Keep or update the wrong-dimension repository test so it still proves invalid embedding dimensions are rejected before persistence.

## 3. Verification

- [x] 3.1 Run the focused backend knowledge RAG test module.
- [x] 3.2 Run OpenSpec validation/status checks for `add-pgvector-bind-compilation-test`.
