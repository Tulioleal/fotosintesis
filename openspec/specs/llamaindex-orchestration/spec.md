## Purpose

Define how trusted knowledge acquisition uses LlamaIndex orchestration for chunking, embedding, pgvector indexing, persistence and degraded behavior.

## Requirements

### Requirement: LlamaIndex ingestion orchestration

The system SHALL use LlamaIndex as the successful acquisition ingestion orchestrator for chunking, embedding creation and pgvector indexing of trusted knowledge, including embedding creation as a LlamaIndex ingestion pipeline transformation rather than a direct app embedding-provider call after pipeline chunking.

#### Scenario: Trusted knowledge is ingested

- **WHEN** trusted knowledge acquisition generates a structured document
- **THEN** the system chunks the document, creates embeddings and indexes retrievable nodes through LlamaIndex orchestration

#### Scenario: App-owned chunking is bypassed for successful acquisition

- **WHEN** acquisition succeeds for newly trusted knowledge
- **THEN** the successful ingestion path does not rely on the app-owned custom chunking function plus direct provider embedding call as the orchestration mechanism

#### Scenario: Embeddings are created inside the LlamaIndex ingestion pipeline

- **WHEN** LlamaIndex ingestion produces trusted knowledge nodes
- **THEN** the embedding provider is invoked through a LlamaIndex pipeline transformation and the orchestration result uses embeddings attached to the produced nodes

### Requirement: Orchestrated artifact persistence

The system SHALL persist LlamaIndex-orchestrated chunks and embedding records with the required botanical and provenance metadata.

#### Scenario: Orchestrated chunks are saved

- **WHEN** LlamaIndex orchestration produces chunks and embeddings for trusted knowledge
- **THEN** the system stores relational document, source, chunk and embedding records containing species, topic, source, confidence, review status and date metadata

### Requirement: Acquisition behavior preservation

The system SHALL preserve trusted-source validation, metadata-filtered re-retrieval and degraded acquisition responses while using LlamaIndex ingestion orchestration.

#### Scenario: Acquisition succeeds after orchestration

- **WHEN** LlamaIndex orchestration and persistence succeed
- **THEN** the system re-runs retrieval using the newly indexed evidence and returns an acquired result

#### Scenario: Orchestration fails

- **WHEN** LlamaIndex chunking, embedding or indexing fails during acquisition
- **THEN** the system returns the best available partial result with limitations and a retry or manual search path

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
