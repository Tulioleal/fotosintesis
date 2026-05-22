## ADDED Requirements

### Requirement: Chat experience

The system SHALL provide a chat API and frontend conversation UI for a plant-care assistant.

#### Scenario: User sends botanical question

- **WHEN** a user sends a supported plant-care question
- **THEN** the system creates or continues a conversation and returns an assistant response

### Requirement: LangGraph orchestration

The backend SHALL use LangGraph nodes for intent classification, user context loading, retrieval, sufficiency evaluation, answer generation, clarification and failure handling.

#### Scenario: Evidence insufficient

- **WHEN** retrieval does not provide enough evidence
- **THEN** the graph routes to acquisition, clarification or limitation handling instead of inventing unsupported facts

### Requirement: Tool-aware assistant

The assistant SHALL use tools for knowledge search, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup when appropriate.

#### Scenario: Missing reminder data

- **WHEN** the user asks the assistant to create a reminder but plant, date, time or recurrence is missing
- **THEN** the assistant asks for the missing information before creating it

### Requirement: RAG-grounded answers

The assistant MUST use retrieved evidence for botanical answers when available and SHALL communicate uncertainty when evidence is limited.

#### Scenario: Evidence-backed answer

- **WHEN** relevant documents are retrieved for a botanical question
- **THEN** the assistant answers using those documents and avoids unsupported claims

### Requirement: Safety and failure handling

The assistant MUST resist prompt injection and MUST NOT claim a failed tool action was completed.

#### Scenario: Tool fails

- **WHEN** a tool call fails during a requested action
- **THEN** the assistant states that the action was not completed and logs the failure
