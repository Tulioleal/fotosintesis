## Purpose

Define how runtime botanical evidence retrieval and trusted knowledge acquisition use LlamaIndex pgvector retrieval, re-embedding and degraded fallback behavior.

## Requirements

### Requirement: Knowledge persistence

The system SHALL persist knowledge documents, sources, chunks and embeddings with required botanical and provenance metadata.

#### Scenario: Knowledge document saved

- **WHEN** new trusted knowledge is ingested
- **THEN** the system stores document content, sources, chunks, embeddings, confidence, review status and timestamps

### Requirement: LlamaIndex pgvector retrieval

The system SHALL use LlamaIndex `PGVectorStore` and `VectorStoreIndex` backed by PostgreSQL + pgvector for runtime botanical evidence retrieval.

#### Scenario: Retrieval by species and topic

- **WHEN** a caller requests evidence for a species and topic
- **THEN** the system retrieves matching chunks through LlamaIndex pgvector retrieval using metadata filters

#### Scenario: SQL-only retrieval path is not used for runtime RAG

- **WHEN** acquisition checks existing evidence or re-runs retrieval after ingestion
- **THEN** the system uses the LlamaIndex-backed retriever instead of direct SQLAlchemy vector scoring

#### Scenario: LlamaIndex dependencies are available

- **WHEN** the backend environment is installed from project dependencies
- **THEN** the LlamaIndex PostgreSQL vector-store integration required by runtime retrieval is installed

### Requirement: Trusted source acquisition

The system MUST restrict incremental acquisition to approved or explicitly validated trusted sources.

#### Scenario: Untrusted source is sole result

- **WHEN** only blogs, stores, unmoderated forums or non-persistent URLs are available
- **THEN** the system does not use them as the sole basis for persistent knowledge

### Requirement: Re-embedding and re-retrieval

The system SHALL create embeddings after successful ingestion, persist them into the LlamaIndex pgvector index with required metadata and allow the caller to re-run retrieval using the new evidence.

#### Scenario: Acquisition succeeds

- **WHEN** a structured knowledge document is generated and persisted
- **THEN** the system chunks, embeds, indexes the chunks through LlamaIndex pgvector and makes them retrievable for the current flow and future flows

#### Scenario: Retrieved evidence maps back to provenance records

- **WHEN** LlamaIndex returns matching vector nodes
- **THEN** the system maps retrieved nodes back to structured knowledge chunks with document, source, confidence, review status and date metadata

### Requirement: Acquisition degradation

The system MUST NOT block the user experience completely when trusted acquisition or LlamaIndex pgvector retrieval fails.

#### Scenario: Trusted acquisition fails

- **WHEN** no trusted source is found or persistence fails
- **THEN** the system returns the best available partial result with limitations and a retry or manual search path

#### Scenario: LlamaIndex retrieval fails

- **WHEN** the LlamaIndex pgvector retriever cannot query or index evidence
- **THEN** the system returns a degraded result with a limitation notice and retry or manual search path instead of silently using SQL-only vector retrieval as the successful path
