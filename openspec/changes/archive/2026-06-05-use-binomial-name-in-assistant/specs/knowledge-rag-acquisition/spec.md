## ADDED Requirements

### Requirement: RAG acquisition plant name priority

Runtime botanical retrieval, trusted web fallback, and fallback evidence acquisition SHALL use the assistant operational plant name derived from `plant_binomial_name`, then `plant_scientific_name`, then `plant`.

#### Scenario: RAG retrieval uses binomial name

- **WHEN** an assistant chat request includes `plant_binomial_name` and RAG retrieval is needed
- **THEN** the retrieval query and species/topic context use `plant_binomial_name` as the plant name

#### Scenario: RAG retrieval falls back to scientific name

- **WHEN** RAG retrieval is needed and `plant_binomial_name` is missing but `plant_scientific_name` is present
- **THEN** the retrieval query and species/topic context use `plant_scientific_name` as the plant name

#### Scenario: Trusted web fallback uses operational name

- **WHEN** persisted RAG evidence is insufficient and trusted web fallback runs for a botanical question
- **THEN** the trusted web search query and any fallback evidence ingestion metadata use the assistant operational plant name

#### Scenario: Legacy plant-only acquisition still works

- **WHEN** an assistant chat request includes only `plant` and retrieval or acquisition is needed
- **THEN** RAG retrieval, trusted web fallback, and fallback evidence acquisition use `plant` as the plant name
