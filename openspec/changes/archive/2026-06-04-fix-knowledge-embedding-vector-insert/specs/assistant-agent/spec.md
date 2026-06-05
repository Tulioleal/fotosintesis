## ADDED Requirements

### Requirement: Fallback persistence failures do not poison chat persistence

The assistant MUST keep fallback evidence persistence failures non-blocking and MUST preserve a usable database session for conversation persistence after those failures.

#### Scenario: Fallback ingestion fails before chat message save

- **WHEN** trusted web fallback evidence is available but fallback evidence ingestion, embedding or indexing fails
- **THEN** the assistant records the persistence failure as non-blocking failure metadata
- **AND** rolls back the failed persistence transaction before saving the assistant chat response

#### Scenario: Chat response continues after fallback persistence failure

- **WHEN** fallback evidence persistence fails after usable trusted evidence was found
- **THEN** the assistant still returns the web-evidence answer with sources
- **AND** the conversation and assistant message can be saved successfully
