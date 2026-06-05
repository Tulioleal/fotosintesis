## ADDED Requirements

### Requirement: Assistant plant naming context

The assistant chat API SHALL accept optional `plant_binomial_name` and `plant_scientific_name` fields in addition to the existing optional `plant` field, and SHALL derive separate operational and display/context plant names from those fields.

#### Scenario: Binomial name is used for operations

- **WHEN** an assistant chat request includes `plant`, `plant_binomial_name`, and `plant_scientific_name`
- **THEN** the assistant uses `plant_binomial_name` as the operational plant name for retrieval, search, API, and acquisition tool calls
- **AND** preserves `plant_scientific_name` as taxonomic context

#### Scenario: Scientific name is operational fallback

- **WHEN** an assistant chat request omits `plant_binomial_name` and includes `plant_scientific_name`
- **THEN** the assistant uses `plant_scientific_name` as the operational plant name

#### Scenario: Legacy plant field remains supported

- **WHEN** an assistant chat request includes only `plant` for plant context
- **THEN** the assistant uses `plant` as both the operational plant name and display/context plant name

#### Scenario: Display context prefers plant label

- **WHEN** an assistant chat request includes `plant` and a different `plant_binomial_name`
- **THEN** the assistant presents `plant` as the primary selected plant context in user-facing chat context
- **AND** may include the binomial name as concise secondary context

### Requirement: Assistant entry URL taxonomy context

The frontend assistant page SHALL read `plant`, `binomial`, and `scientific` query parameters and send them to the assistant chat API as `plant`, `plant_binomial_name`, and `plant_scientific_name` respectively.

#### Scenario: Assistant route maps query parameters to payload

- **WHEN** the assistant page is opened with `plant`, `binomial`, and `scientific` query parameters and the user sends a message
- **THEN** the chat request payload includes the display plant, binomial plant name, and full scientific plant name in the corresponding backend fields

#### Scenario: Assistant UI shows concise context

- **WHEN** both display plant and binomial name are available on the assistant page
- **THEN** the assistant UI shows the display plant as the initial context and the binomial name as secondary context
- **AND** does not show a more verbose full scientific name by default when the binomial name is present

#### Scenario: Identification entry passes taxonomy names

- **WHEN** a user opens the assistant from an identification result with common, binomial, and accepted or suggested scientific names
- **THEN** the assistant link uses the common name when available as `plant`, the binomial name as `binomial`, and the accepted or suggested scientific name as `scientific`

#### Scenario: Garden profile entry passes available binomial context

- **WHEN** a user opens the assistant from a garden or plant profile view that exposes both `binomial_name` and `scientific_name`
- **THEN** the assistant link includes both `binomial` and `scientific` query parameters
