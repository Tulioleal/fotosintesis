## MODIFIED Requirements

### Requirement: GBIF taxonomy validation

The system SHALL validate and normalize candidate scientific names against GBIF Species API before definitive use.

#### Scenario: Candidate validated by GBIF

- **WHEN** GBIF normalizes a candidate name
- **THEN** the system persists stable identifier, accepted name, synonyms, genus, family, species metadata, and optional binomial name without losing the original scientific identification context

#### Scenario: GBIF provides canonical name

- **WHEN** GBIF returns a reliable canonical name for a validated candidate
- **THEN** the system persists and returns that value as `binomial_name`

#### Scenario: GBIF omits reliable binomial name

- **WHEN** GBIF does not provide a reliable canonical name and genus plus species are incomplete
- **THEN** the system persists and returns `binomial_name` as null while retaining the available taxonomic fields
