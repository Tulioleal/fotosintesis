## ADDED Requirements

### Requirement: Assistant fallback web evidence persistence

The system SHALL persist assistant fallback web evidence through the existing trusted knowledge ingestion path when web-search results are used to answer after insufficient RAG evidence.

#### Scenario: Fallback evidence is ingested

- **WHEN** the assistant answers a botanical question from trusted web-search results because RAG evidence was insufficient
- **THEN** the system builds a knowledge document from the web snippets and source metadata, marks it `auto_ingested`, and ingests it through the LlamaIndex-backed knowledge vector index

#### Scenario: Fallback evidence is embedded and indexed

- **WHEN** fallback web evidence ingestion succeeds
- **THEN** the system chunks, embeds, persists and indexes the evidence using the configured embedding provider so future retrieval can find it

#### Scenario: Fallback evidence persistence is best effort

- **WHEN** fallback evidence ingestion, embedding or indexing fails after usable web evidence was found
- **THEN** the system does not block the assistant answer and records the persistence limitation for observability or response metadata
