## ADDED Requirements

### Requirement: Structured lookup operational plant name

Structured plant-data lookup SHALL use the assistant operational plant name derived from `plant_binomial_name`, then `plant_scientific_name`, then `plant`, and MUST continue to treat that value as already-confirmed plant context rather than an identification request.

#### Scenario: Structured lookup uses binomial name first

- **WHEN** RAG evidence is insufficient and an assistant chat request includes `plant_binomial_name`
- **THEN** `plant_data_lookup` is called with `plant_binomial_name` as the scientific-name input

#### Scenario: Structured lookup falls back to scientific name

- **WHEN** RAG evidence is insufficient, `plant_binomial_name` is missing, and `plant_scientific_name` is present
- **THEN** `plant_data_lookup` is called with `plant_scientific_name` as the scientific-name input

#### Scenario: Structured lookup preserves legacy plant fallback

- **WHEN** RAG evidence is insufficient and the request includes only `plant`
- **THEN** existing plant-only assistant payloads can still call `plant_data_lookup` with `plant` when the plant context is otherwise confirmed
