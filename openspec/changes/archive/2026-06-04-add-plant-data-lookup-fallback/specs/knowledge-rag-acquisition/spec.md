## ADDED Requirements

### Requirement: Structured API fallback before trusted web acquisition
The system SHALL attempt structured plant-data API evidence after LlamaIndex pgvector retrieval is unavailable or insufficient and before trusted web search/page-fetch acquisition.

#### Scenario: RAG evidence is sufficient
- **WHEN** LlamaIndex pgvector retrieval returns sufficient evidence for the confirmed scientific name and topic
- **THEN** the system answers from retrieved evidence without calling Trefle, Perenual or trusted web search

#### Scenario: RAG evidence is insufficient
- **WHEN** LlamaIndex pgvector retrieval returns no usable chunks or insufficient chunks for the confirmed scientific name and topic
- **THEN** the system attempts structured plant-data lookup before trusted web search

#### Scenario: Structured API evidence is insufficient
- **WHEN** Trefle is unavailable or insufficient and Perenual is unavailable or still insufficient for the requested topic
- **THEN** the system continues to the existing trusted web search/page-fetch fallback

## MODIFIED Requirements

### Requirement: Acquisition degradation
The system MUST NOT block the user experience completely when structured plant-data lookup, trusted acquisition or LlamaIndex pgvector retrieval fails.

#### Scenario: Structured plant-data lookup fails
- **WHEN** structured plant-data providers are unavailable or return insufficient evidence
- **THEN** the system continues to trusted web search/page-fetch fallback before returning a manual search or degraded response

#### Scenario: Trusted acquisition fails
- **WHEN** no trusted source is found or persistence fails after structured plant-data lookup has been attempted where eligible
- **THEN** the system returns the best available partial result with limitations and a retry or manual search path

#### Scenario: LlamaIndex retrieval fails
- **WHEN** the LlamaIndex pgvector retriever cannot query or index evidence
- **THEN** the system attempts eligible structured plant-data lookup and then returns a degraded result with a limitation notice and retry or manual search path instead of silently using SQL-only vector retrieval as the successful path
