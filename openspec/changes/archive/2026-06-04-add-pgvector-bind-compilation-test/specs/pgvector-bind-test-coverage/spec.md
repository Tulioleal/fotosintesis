## ADDED Requirements

### Requirement: Pgvector insert bind compilation coverage

The backend test suite SHALL include regression coverage that verifies knowledge embedding inserts compile with a pgvector-compatible binding for `knowledge_embeddings.embedding_vector` under the PostgreSQL dialect.

#### Scenario: Repository embedding insert binds vector type

- **WHEN** the repository embedding insert path is exercised or an equivalent `knowledge_embeddings` insert statement is compiled with the PostgreSQL dialect
- **THEN** the `embedding_vector` value is associated with the pgvector SQLAlchemy type rather than a text or `VARCHAR` type

#### Scenario: Dimension validation coverage remains intact

- **WHEN** an embedding with the wrong configured dimension is passed to the repository
- **THEN** the backend tests still verify the embedding is rejected before persistence
