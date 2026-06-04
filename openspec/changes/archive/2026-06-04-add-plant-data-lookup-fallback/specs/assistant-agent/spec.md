## MODIFIED Requirements

### Requirement: Tool-aware assistant
The assistant SHALL use tools for knowledge search, structured plant-data lookup, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup when appropriate. The assistant SHALL expose structured reminder suggestions for user confirmation when it proposes a reminder from conversation context instead of directly creating one.

#### Scenario: Missing reminder data
- **WHEN** the user asks the assistant to create a reminder but plant, date, time or recurrence is missing
- **THEN** the assistant asks for the missing information before creating it

#### Scenario: Reminder suggestion requires confirmation
- **WHEN** the assistant proposes a reminder from conversation context and has plant, action, due date, due time and recurrence values
- **THEN** the assistant response includes an actionable reminder suggestion with the plant, action, due timestamp, recurrence and justification instead of relying only on message text

#### Scenario: Structured lookup follows insufficient RAG
- **WHEN** knowledge search returns insufficient evidence for a botanical question with one confirmed scientific name
- **THEN** the assistant calls `plant_data_lookup` before `trusted_web_search`

#### Scenario: Structured lookup requires confirmed plant
- **WHEN** plant context is missing, ambiguous or unconfirmed
- **THEN** the assistant asks for clarification or confirmation instead of calling `plant_data_lookup`

### Requirement: RAG-grounded answers
The assistant MUST use retrieved or structured provider evidence for botanical answers when available and SHALL communicate uncertainty when evidence is limited.

#### Scenario: Evidence-backed answer
- **WHEN** relevant documents are retrieved for a botanical question
- **THEN** the assistant answers using those documents and avoids unsupported claims

#### Scenario: Structured API-backed answer
- **WHEN** vector retrieval is insufficient and structured API evidence is sufficient
- **THEN** the assistant answers using normalized structured evidence with provider attribution and avoids unsupported claims

#### Scenario: Structured evidence insufficient
- **WHEN** vector retrieval and structured API evidence are both insufficient
- **THEN** the assistant continues to trusted web search/page-fetch fallback before returning a manual search or degraded response
