## ADDED Requirements

### Requirement: LlamaIndex ingestion orchestration

The system SHALL use LlamaIndex as the successful acquisition ingestion orchestrator for chunking, embedding creation and pgvector indexing of trusted knowledge.

#### Scenario: Trusted knowledge is ingested

- **WHEN** trusted knowledge acquisition generates a structured document
- **THEN** the system chunks the document, creates embeddings and indexes retrievable nodes through LlamaIndex orchestration

#### Scenario: App-owned chunking is bypassed for successful acquisition

- **WHEN** acquisition succeeds for newly trusted knowledge
- **THEN** the successful ingestion path does not rely on the app-owned custom chunking function plus direct provider embedding call as the orchestration mechanism

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
