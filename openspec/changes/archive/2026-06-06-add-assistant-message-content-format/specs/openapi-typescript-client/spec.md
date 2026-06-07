## ADDED Requirements

### Requirement: Assistant message format generated contract

The frontend SHALL regenerate and consume OpenAPI TypeScript contracts that include the assistant message `content_format` field as an enum-compatible value.

#### Scenario: Generated assistant message includes content format

- **WHEN** OpenAPI TypeScript generation is run after the backend assistant schema update
- **THEN** the generated `AssistantMessage` type includes `content_format`
- **AND** the field is compatible with the closed values `plain_text` and `markdown`

#### Scenario: Frontend uses generated assistant message format

- **WHEN** frontend assistant chat code renders an assistant response
- **THEN** it obtains the response message content format from the generated assistant API type
- **AND** does not define a manually divergent assistant response shape
