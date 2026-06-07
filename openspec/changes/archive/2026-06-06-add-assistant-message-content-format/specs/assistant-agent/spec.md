## ADDED Requirements

### Requirement: Assistant message content format contract

The assistant chat API SHALL expose an explicit `content_format` field on `AssistantMessage`. Backend and frontend representations of assistant message content format SHALL be limited to `plain_text` and `markdown`, and `plain_text` SHALL be the default format.

#### Scenario: Assistant response declares plain-text format

- **WHEN** an assistant response is generated
- **THEN** the API response message includes `content_format: "plain_text"`
- **AND** the persisted assistant message metadata includes `content_format: "plain_text"`

#### Scenario: Closed content format values

- **WHEN** assistant message content format is represented in backend or frontend types
- **THEN** it is limited to `plain_text` and `markdown`
- **AND** `plain_text` is the default format

#### Scenario: Existing messages remain compatible

- **WHEN** a message lacks `content_format`
- **THEN** consumers treat it as `plain_text`
- **AND** no database migration is required for existing message metadata

### Requirement: Plain-text model output

The backend SHALL instruct the language model to produce plain-text assistant answers for the current chat UI.

#### Scenario: Model is instructed to avoid Markdown

- **WHEN** the backend builds the model prompt for assistant answer synthesis
- **THEN** the prompt instructs the model to output plain text only
- **AND** forbids Markdown, HTML, tables, code blocks, headings and bullet lists

### Requirement: Format-aware frontend rendering

The frontend SHALL render assistant message content through a format-aware rendering boundary.

#### Scenario: Frontend preserves plain-text line breaks

- **WHEN** the frontend renders an assistant message containing newline characters
- **THEN** the visible message preserves those line breaks as plain text

#### Scenario: Frontend tolerates not-yet-rendered formats

- **WHEN** the frontend receives a message with `content_format: "markdown"`
- **THEN** it renders the raw content as plain text
- **AND** does not parse Markdown
- **AND** does not throw

#### Scenario: Frontend defaults missing format

- **WHEN** the frontend renders an assistant message that lacks `content_format`
- **THEN** it renders the raw content as plain text
- **AND** treats the message as `plain_text`
