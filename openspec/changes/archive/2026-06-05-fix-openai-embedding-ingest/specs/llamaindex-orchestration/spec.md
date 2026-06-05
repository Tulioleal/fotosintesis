## ADDED Requirements

### Requirement: OpenAI embedding ingestion compatibility
The system SHALL create embeddings through the OpenAI embedding provider during LlamaIndex ingestion without forwarding app-only metadata to the OpenAI SDK, and SHALL request vectors using the configured embedding dimension when OpenAI is the configured embedding provider.

#### Scenario: LlamaIndex metadata is not sent to OpenAI embeddings
- **WHEN** LlamaIndex ingestion invokes the configured OpenAI embedding provider with node metadata
- **THEN** the provider creates embeddings without passing `metadata` to the OpenAI embeddings SDK
- **AND** the ingestion metadata remains available for persistence and retrieval metadata handling outside the OpenAI SDK request

#### Scenario: OpenAI embedding dimensions match pgvector configuration
- **WHEN** OpenAI embeddings are requested for RAG ingestion and `EMBEDDING_DIMENSION` is configured
- **THEN** the provider passes that configured dimension as the OpenAI embeddings `dimensions` parameter for compatible embedding models
- **AND** the returned vectors are suitable for insertion into the configured pgvector embedding column

#### Scenario: Mock embedding provider remains permissive
- **WHEN** the mock embedding provider receives metadata or other ingestion keyword arguments during tests or local development
- **THEN** it continues to accept those arguments without failing the ingestion flow
