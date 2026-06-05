## ADDED Requirements

### Requirement: Separated plant taxonomy context
The assistant chat flow SHALL accept separated plant display, binomial and scientific-name context from the frontend while preserving support for existing requests that only provide a plant string.

#### Scenario: Chat request includes binomial and scientific context
- **WHEN** the assistant page is opened with `plant`, `binomial` and `scientific` query parameters
- **THEN** the frontend sends `plant`, `plant_binomial_name` and `plant_scientific_name` in the assistant chat request

#### Scenario: Binomial context preferred for plant operations
- **WHEN** an assistant chat request includes `plant_binomial_name`
- **THEN** the assistant uses the binomial name as the preferred plant context for botanical search, structured lookup and retrieval operations

#### Scenario: Plant-only chat remains compatible
- **WHEN** the assistant page or request only provides `plant`
- **THEN** the chat flow continues to send and process the request without requiring binomial or scientific-name fields
