## ADDED Requirements

### Requirement: Assistant chat generated taxonomy fields

The frontend SHALL regenerate and consume OpenAPI TypeScript contracts that include optional nullable `plant_binomial_name` and `plant_scientific_name` assistant chat request fields.

#### Scenario: Generated assistant request includes taxonomy fields

- **WHEN** OpenAPI TypeScript generation is run after the backend assistant schema update
- **THEN** the generated assistant chat request type includes `plant_binomial_name` and `plant_scientific_name` as optional nullable fields

#### Scenario: Frontend chat client sends taxonomy fields

- **WHEN** frontend assistant chat code sends a request with binomial and scientific query context
- **THEN** the frontend API wrapper accepts and forwards `plant_binomial_name` and `plant_scientific_name` without manually diverging from the generated contract
