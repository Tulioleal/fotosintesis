## Purpose

Define structured plant-data lookup behavior, provider ordering, normalization, ingestion and runtime configuration for botanical evidence fallback.

## Requirements

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

### Requirement: Structured provider runtime configuration

The backend SHALL configure Trefle and Perenual credentials only where required for backend runtime provider construction, while deterministic mock providers SHALL remain available without external credentials.

#### Scenario: Mock providers selected

- **WHEN** deterministic mock structured plant-data providers are selected for tests or local default behavior
- **THEN** backend startup and provider construction do not require Trefle or Perenual credentials

#### Scenario: Real provider missing credentials

- **WHEN** a real Trefle or Perenual provider is selected without its required credentials
- **THEN** provider construction fails with a clear backend configuration error for that provider

### Requirement: Structured lookup operational plant name

Structured plant-data lookup SHALL use the assistant operational plant name derived from `plant_binomial_name`, then a safe binomial derived from `plant_scientific_name`, then normalized `plant_scientific_name` when no safe binomial can be derived, then `plant` only for legacy flows that already permit plant-only confirmed context. Structured lookup MUST continue to treat that value as already-confirmed plant context rather than an identification request when a flow explicitly uses structured lookup. The normal assistant chat-time plant-care answer path SHALL prefer the same operational plant name for RAG and web evidence operations but SHALL NOT use it to call structured lookup in that path.

#### Scenario: Structured lookup uses binomial name first outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup and includes `plant_binomial_name`
- **THEN** `plant_data_lookup` is called with `plant_binomial_name` as the scientific-name input

#### Scenario: Structured lookup derives binomial from authority scientific name outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` is `Epipremnum aureum (Linden & André) G.S.Bunting`
- **THEN** `plant_data_lookup` is called with `Epipremnum aureum` as the scientific-name input

#### Scenario: Structured lookup derives binomial from infraspecific scientific name outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` is `Solanum lycopersicum var. cerasiforme`
- **THEN** `plant_data_lookup` is called with `Solanum lycopersicum` as the scientific-name input

#### Scenario: Structured lookup falls back to normalized scientific name outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` cannot safely produce a two-token Latin binomial
- **THEN** `plant_data_lookup` is called with the normalized `plant_scientific_name` as the scientific-name input

#### Scenario: Legacy plant fallback remains outside normal chat-time path

- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup and includes only `plant`
- **THEN** existing plant-only assistant payloads can still call `plant_data_lookup` with `plant` when the plant context is otherwise confirmed

#### Scenario: Chat-time path uses operational name for RAG and web only

- **WHEN** the assistant normal plant-care chat path has operational plant context
- **THEN** it uses that context for RAG retrieval and trusted web search
- **AND** it does not call `plant_data_lookup` in that path
