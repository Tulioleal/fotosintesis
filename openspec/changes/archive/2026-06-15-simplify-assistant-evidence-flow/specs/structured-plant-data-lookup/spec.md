## MODIFIED Requirements

### Requirement: Structured plant-data lookup contract

The system SHALL provide a `plant_data_lookup` tool that accepts an already-confirmed scientific name and a requested topic, and MUST NOT use structured plant-data providers to identify, match or disambiguate plants. The normal assistant chat-time plant-care answer path SHALL NOT call `plant_data_lookup` between non-full RAG evidence and trusted web search.

#### Scenario: Lookup uses confirmed scientific name outside normal chat-time path

- **WHEN** an eligible non-chat-time backend flow or future offline ingestion flow has one confirmed scientific name and a requested topic
- **THEN** that flow may call `plant_data_lookup` with that scientific name and the requested topic

#### Scenario: Chat-time care answer skips structured lookup

- **WHEN** the assistant normal plant-care chat path has RAG evidence that is partial, insufficient, contradictory, missing or degraded
- **THEN** the assistant proceeds to trusted web search before final answer generation
- **AND** the assistant does not call Trefle, Perenual, or `plant_data_lookup` as an intermediate fallback

#### Scenario: Identification is not performed

- **WHEN** the assistant has an unconfirmed plant name, ambiguous plant context or an identification request
- **THEN** the assistant does not call Trefle, Perenual or `plant_data_lookup` for plant identification or disambiguation

### Requirement: Structured evidence best-effort ingestion

The system SHALL save and index normalized structured API evidence through the existing auto-ingested knowledge flow without marking it `needs_review` when a non-chat-time backend flow explicitly uses structured API evidence. Normal assistant chat-time plant-care answer generation SHALL NOT block on structured evidence ingestion because it does not call structured plant-data lookup in that path.

#### Scenario: Structured evidence persistence succeeds outside normal chat-time path

- **WHEN** structured API evidence is used by an eligible non-chat-time backend flow
- **THEN** the system attempts to persist and index it with auto-ingested review status for future retrieval

#### Scenario: Structured evidence persistence fails outside normal chat-time path

- **WHEN** structured API evidence is sufficient for the current non-chat-time flow but persistence or pgvector indexing fails
- **THEN** the flow records the persistence or indexing failure as non-blocking according to its caller contract

#### Scenario: Chat-time path has no structured ingestion delay

- **WHEN** the assistant normal plant-care chat path answers after RAG and trusted web evidence evaluation
- **THEN** the response is not delayed by structured API evidence persistence or indexing

### Requirement: Structured lookup operational plant name

Structured plant-data lookup SHALL use the assistant operational plant name derived from `plant_binomial_name`, then `plant_scientific_name`, then `plant`, and MUST continue to treat that value as already-confirmed plant context rather than an identification request when a flow explicitly uses structured lookup. The normal assistant chat-time plant-care answer path SHALL prefer the same operational plant name for RAG and web evidence operations but SHALL NOT use it to call structured lookup in that path.

#### Scenario: Structured lookup uses binomial name first outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup and includes `plant_binomial_name`
- **THEN** `plant_data_lookup` is called with `plant_binomial_name` as the scientific-name input

#### Scenario: Structured lookup falls back to scientific name outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` is present
- **THEN** `plant_data_lookup` is called with `plant_scientific_name` as the scientific-name input

#### Scenario: Legacy plant fallback remains outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup and includes only `plant`
- **THEN** existing plant-only payloads can still call `plant_data_lookup` with `plant` when the plant context is otherwise confirmed

#### Scenario: Chat-time path uses operational name for RAG and web only

- **WHEN** the assistant normal plant-care chat path has operational plant context
- **THEN** it uses that context for RAG retrieval and trusted web search
- **AND** it does not call `plant_data_lookup` in that path
