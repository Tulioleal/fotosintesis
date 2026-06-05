## Why

The pgvector persistence fix currently verifies table metadata but does not directly prove that embedding inserts compile with a pgvector-compatible bind under the PostgreSQL dialect. A focused regression test will close that verification gap before the fix is archived or extended.

## What Changes

- Add a backend repository/SQL compilation regression test for `knowledge_embeddings.embedding_vector` inserts.
- Assert the generated PostgreSQL insert path binds `embedding_vector` with the pgvector SQLAlchemy type rather than `VARCHAR`/text.
- Preserve the existing dimension validation regression coverage without changing runtime persistence behavior.

## Capabilities

### New Capabilities

- `pgvector-bind-test-coverage`: Regression coverage proving repository embedding inserts use pgvector-compatible SQLAlchemy binding under PostgreSQL compilation.

### Modified Capabilities

## Impact

- Affected tests: `backend/tests/test_knowledge_rag.py` or an adjacent backend repository test module.
- Affected runtime code: none expected.
- Affected dependencies/APIs: none expected.
