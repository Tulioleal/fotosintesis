## ADDED Requirements

### Requirement: Pgvector embedding persistence contract

The system SHALL persist knowledge embedding vectors using a database binding compatible with the PostgreSQL pgvector column type and the configured embedding dimension.

#### Scenario: Embedding vector insert uses pgvector-compatible binding

- **WHEN** a knowledge chunk embedding is persisted to `knowledge_embeddings.embedding_vector`
- **THEN** the insert value is bound or cast as a pgvector-compatible vector value rather than as `VARCHAR`

#### Scenario: Embedding dimension remains validated

- **WHEN** an embedding dimension does not match the configured embedding dimension
- **THEN** the system rejects the embedding before persisting it

### Requirement: JSON formatted acquisition prompt

The system SHALL make structured knowledge acquisition prompts compatible with provider JSON object response formatting.

#### Scenario: OpenAI JSON object formatting is requested

- **WHEN** the acquisition flow calls the configured model provider with JSON object response formatting
- **THEN** the input prompt explicitly instructs the provider to return JSON

### Requirement: Acquisition failure transaction recovery

The system MUST recover the active database transaction after best-effort knowledge acquisition persistence or embedding failure before continuing with later database writes.

#### Scenario: Best-effort acquisition persistence fails

- **WHEN** trusted knowledge acquisition, embedding persistence or vector indexing fails in a path that continues execution
- **THEN** the system rolls back the failed transaction before performing subsequent database writes
