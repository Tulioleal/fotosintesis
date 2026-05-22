## ADDED Requirements

### Requirement: Knowledge persistence

The system SHALL persist knowledge documents, sources, chunks and embeddings with required botanical and provenance metadata.

#### Scenario: Knowledge document saved

- **WHEN** new trusted knowledge is ingested
- **THEN** the system stores document content, sources, chunks, embeddings, confidence, review status and timestamps

### Requirement: LlamaIndex pgvector retrieval

The system SHALL use LlamaIndex with PostgreSQL + pgvector to retrieve relevant botanical evidence.

#### Scenario: Retrieval by species and topic

- **WHEN** a caller requests evidence for a species and topic
- **THEN** the system retrieves matching chunks from pgvector using metadata filters

### Requirement: Trusted source acquisition

The system MUST restrict incremental acquisition to approved or explicitly validated trusted sources.

#### Scenario: Untrusted source is sole result

- **WHEN** only blogs, stores, unmoderated forums or non-persistent URLs are available
- **THEN** the system does not use them as the sole basis for persistent knowledge

### Requirement: Re-embedding and re-retrieval

The system SHALL create embeddings after successful ingestion and allow the caller to re-run retrieval using the new evidence.

#### Scenario: Acquisition succeeds

- **WHEN** a structured knowledge document is generated and persisted
- **THEN** the system chunks, embeds and makes it retrievable for the current flow and future flows

### Requirement: Acquisition degradation

The system MUST NOT block the user experience completely when trusted acquisition fails.

#### Scenario: Trusted acquisition fails

- **WHEN** no trusted source is found or persistence fails
- **THEN** the system returns the best available partial result with limitations and a retry or manual search path
