## MODIFIED Requirements

### Requirement: Assistant fallback web evidence persistence

The system SHALL persist assistant fallback web evidence through the existing knowledge ingestion path only when selected web-search results are independently validated for at least one requested missing care aspect. Trusted-domain fallback evidence SHALL retain trusted provenance, while selected external fallback evidence SHALL be persisted as lower-confidence auto-ingested evidence with source validation status `external_fallback`. Each independently validated fallback source SHALL be persisted as a separate knowledge document with source-specific covered aspects and validation confidence.

#### Scenario: Trusted fallback evidence is ingested

- **WHEN** the assistant answers a botanical question from trusted web-search results because RAG evidence was insufficient
- **THEN** the system builds one knowledge document per independently validated trusted source from that source's web snippet or fetched page content and source metadata, marks each document `auto_ingested`, and ingests each document through the LlamaIndex-backed knowledge vector index
- **AND** each source validation status remains trusted

#### Scenario: External fallback evidence is ingested

- **WHEN** the assistant answers a botanical question from one selected external fallback web result because RAG evidence was insufficient and no allowed-domain search results were returned
- **THEN** the system builds a knowledge document from that independently validated fallback evidence and source metadata
- **AND** the document is marked `auto_ingested`
- **AND** the document confidence is lower than trusted-domain web evidence confidence
- **AND** the source validation status is `external_fallback`

#### Scenario: Fallback evidence is embedded and indexed

- **WHEN** fallback web evidence ingestion succeeds for an independently validated source
- **THEN** the system chunks, embeds, persists and indexes that source's evidence using the configured embedding provider so future retrieval can find it

#### Scenario: Fallback evidence persistence is best effort

- **WHEN** fallback web evidence ingestion, embedding or indexing fails after usable web evidence was found
- **THEN** the system does not block the assistant answer and records the persistence limitation for observability or response metadata

#### Scenario: Off-aspect fallback evidence is not persisted

- **WHEN** assistant fallback web search returns a trusted source that does not independently validate for any requested missing aspect
- **THEN** the system does not persist, chunk, embed or vector-index that source

#### Scenario: Source-specific aspects are persisted

- **WHEN** multiple fallback web sources independently validate for different requested missing aspects
- **THEN** the system persists each validated source as a separate knowledge document
- **AND** each document metadata includes only that source's validated `covered_aspects`
- **AND** each document metadata includes that source's validation confidence

#### Scenario: Overall web validation confidence remains conservative

- **WHEN** multiple independently validated web sources are used for one fallback answer
- **THEN** the fallback answer's overall web validation confidence is the minimum validation confidence among the included validated sources
