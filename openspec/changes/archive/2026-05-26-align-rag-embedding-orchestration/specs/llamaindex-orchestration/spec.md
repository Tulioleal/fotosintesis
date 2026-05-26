## MODIFIED Requirements

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
