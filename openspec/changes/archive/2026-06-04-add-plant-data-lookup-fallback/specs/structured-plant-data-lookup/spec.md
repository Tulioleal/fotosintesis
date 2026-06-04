## ADDED Requirements

### Requirement: Structured plant-data lookup contract
The system SHALL provide a `plant_data_lookup` tool that accepts an already-confirmed scientific name and a requested topic, and MUST NOT use structured plant-data providers to identify, match or disambiguate plants.

#### Scenario: Lookup uses confirmed scientific name
- **WHEN** the assistant has one confirmed scientific name and RAG evidence is insufficient or unavailable
- **THEN** the assistant may call `plant_data_lookup` with that scientific name and the requested topic

#### Scenario: Identification is not performed
- **WHEN** the assistant has an unconfirmed plant name, ambiguous plant context or an identification request
- **THEN** the assistant does not call Trefle, Perenual or `plant_data_lookup` for plant identification or disambiguation

### Requirement: Trefle-first provider order
The system SHALL query Trefle before Perenual for structured botanical/species evidence and SHALL evaluate Trefle sufficiency before deciding whether another structured provider is needed.

#### Scenario: Trefle evidence is sufficient
- **WHEN** Trefle returns sufficient evidence for the requested scientific name and topic
- **THEN** the system uses Trefle evidence and does not call Perenual for that lookup

#### Scenario: Trefle evidence is insufficient for care topic
- **WHEN** Trefle returns botanical evidence but lacks requested care-specific fields such as watering, sunlight, soil, maintenance, pests or care guidance
- **THEN** the system calls Perenual to complement only the missing care-specific evidence

### Requirement: Structured evidence normalization and attribution
The system SHALL normalize Trefle and Perenual responses into the internal evidence model with provider attribution suitable for answer generation and knowledge ingestion.

#### Scenario: Providers return complementary evidence
- **WHEN** Trefle and Perenual both provide usable fields for a lookup
- **THEN** the system merges the evidence into a single normalized evidence result while preserving per-provider source attribution

#### Scenario: Concise attributed answer
- **WHEN** normalized structured evidence is sufficient to answer the user question
- **THEN** the assistant returns a concise answer that identifies the structured provider sources used

### Requirement: Structured evidence best-effort ingestion
The system SHALL save and index normalized structured API evidence through the existing auto-ingested knowledge flow without marking it `needs_review`, and MUST NOT block the user response if persistence or pgvector indexing fails.

#### Scenario: Structured evidence persistence succeeds
- **WHEN** structured API evidence is used for an answer
- **THEN** the system attempts to persist and index it with auto-ingested review status for future retrieval

#### Scenario: Structured evidence persistence fails
- **WHEN** structured API evidence is sufficient for the current answer but persistence or pgvector indexing fails
- **THEN** the assistant still returns the answer and records the persistence or indexing failure as a non-blocking tool failure

### Requirement: Structured provider runtime configuration
The backend SHALL configure Trefle and Perenual credentials only where required for backend runtime provider construction, while deterministic mock providers SHALL remain available without external credentials.

#### Scenario: Mock providers selected
- **WHEN** deterministic mock structured plant-data providers are selected for tests or local default behavior
- **THEN** backend startup and provider construction do not require Trefle or Perenual credentials

#### Scenario: Real provider missing credentials
- **WHEN** a real Trefle or Perenual provider is selected without its required credentials
- **THEN** provider construction fails with a clear backend configuration error for that provider
