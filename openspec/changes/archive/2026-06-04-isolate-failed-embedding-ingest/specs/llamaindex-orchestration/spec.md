## ADDED Requirements

### Requirement: Embedding dimensions are validated before pgvector writes
The system SHALL validate embedding vector dimensions against the configured embedding dimension before persisting or indexing embeddings in PostgreSQL pgvector.

#### Scenario: Wrong-sized persisted embedding is rejected before SQL insert
- **WHEN** knowledge embedding persistence receives an embedding whose vector length does not match the configured embedding dimension
- **THEN** the system rejects the embedding with a clear application error before executing the pgvector insert
- **AND** the database transaction is not aborted by a pgvector dimension error

#### Scenario: OpenAI returns unexpected embedding dimensions
- **WHEN** the OpenAI embedding provider is configured with an expected embedding dimension and the OpenAI response contains a vector with a different dimension
- **THEN** the provider rejects the response with an OpenAI provider error
- **AND** the wrong-sized vector is not returned to RAG ingestion or database persistence

#### Scenario: Correct-sized embeddings continue to persist
- **WHEN** LlamaIndex orchestration produces embeddings whose lengths match the configured embedding dimension
- **THEN** the system persists and indexes the embeddings through the existing knowledge/vector-index path
