## Purpose

TBD - Defines the assistant-agent capability for plant-care chat, orchestration, tools, grounded answers, and safe failure handling.

## Requirements

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

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded only in supplied evidence, SHALL communicate uncertainty proportionally and briefly when evidence is limited, incomplete or degraded while still giving a practical evidence-backed answer when safe, and MUST preserve source attribution in the assistant API response. When persisted retrieval is insufficient and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets, while still answering from trusted snippets when page fetching fails. When synthesizing a structured API-backed answer, the assistant MUST explicitly instruct the model to mention the structured provider sources used in the final user-facing answer. If model generation fails, the assistant SHALL return a deterministic evidence summary and record the model failure as a non-blocking tool failure.

#### Scenario: Evidence-backed answer

- **WHEN** relevant documents are retrieved for a botanical question
- **THEN** the assistant generates the final response with the configured model using those documents and avoids unsupported claims

#### Scenario: Structured evidence-backed answer

- **WHEN** RAG evidence is insufficient and structured plant-data evidence is sufficient for a botanical question
- **THEN** the assistant generates the final response with the configured model using the structured evidence and provider metadata, and explicitly instructs the model to mention the structured provider sources used

#### Scenario: Trusted web evidence-backed answer

- **WHEN** RAG and structured plant-data evidence are insufficient and trusted web evidence is available
- **THEN** the assistant generates the final response with the configured model using trusted web evidence and source metadata

#### Scenario: Structured evidence insufficient

- **WHEN** vector retrieval and structured API evidence are both insufficient
- **THEN** the assistant continues to trusted web search/page-fetch fallback before returning a manual search or degraded response

#### Scenario: Fetched trusted page content used for fallback answer

- **WHEN** persisted retrieval is insufficient and trusted live web fallback returns extracted page content
- **THEN** the assistant answer uses the extracted trusted page content and does not rely only on original citation or snippet markdown

#### Scenario: Trusted snippet used when page fetch fails

- **WHEN** persisted retrieval is insufficient and trusted live web fallback has a trusted search result whose page fetch fails
- **THEN** the assistant still answers using the trusted snippet and no fetch exception blocks the response

#### Scenario: Model synthesis fails

- **WHEN** model generation fails while evidence is available for a botanical answer
- **THEN** the assistant returns a deterministic summary from the available evidence and records the model failure without dropping source attribution

### Requirement: Fetched fallback evidence context

The assistant SHALL include fetched trusted page content in fallback answer evidence context when that content is available.

#### Scenario: Fetched content supports fallback answer

- **WHEN** existing RAG evidence is insufficient and fallback web search yields trusted results with successfully extracted page content
- **THEN** the assistant generates its fallback answer using the extracted page content rather than only search snippets
- **AND** cites the corresponding trusted source URLs in the response sources

#### Scenario: Fallback answer degrades to snippets

- **WHEN** fallback web search yields trusted results but page fetch or extraction fails
- **THEN** the assistant generates its fallback answer from the trusted result snippets
- **AND** does not claim that full page content was acquired

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted web search for botanical questions when retrieved RAG evidence is insufficient and a specific plant context is available.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning clarification or limitation text

#### Scenario: Web fallback answer uses live evidence

- **WHEN** trusted web search returns usable results after insufficient RAG evidence
- **THEN** the assistant answers from the web result snippets, identifies the evidence as live web evidence, and avoids presenting it as reviewed persisted knowledge

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources for the web result URLs, titles, domains and confidence context

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted web search fails or returns no usable results after insufficient RAG evidence
- **THEN** the assistant returns the existing degraded limitation or manual-search guidance instead of inventing unsupported botanical facts

### Requirement: Web fallback failures are tracked without blocking answers

The assistant MUST record trusted web-search or fallback persistence failures in tool failure metadata while still returning an answer when usable web evidence is available.

#### Scenario: Search fails before fallback answer

- **WHEN** trusted web search fails and no sufficient RAG evidence exists
- **THEN** the assistant records the search failure and returns limitation or manual-search guidance

#### Scenario: Persistence fails after fallback answer evidence exists

- **WHEN** trusted web search returns usable evidence but fallback evidence persistence fails
- **THEN** the assistant records the persistence failure and still returns the web-evidence answer with sources

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

### Requirement: Tool ingestion failures preserve chat persistence

The assistant SHALL keep the chat database session usable after best-effort knowledge ingestion fails inside an assistant tool and is reported as a non-blocking tool failure.

#### Scenario: Structured ingestion failure does not abort assistant response save

- **WHEN** structured plant-data evidence is available but its knowledge ingestion fails after database work has started
- **THEN** the assistant records the ingestion failure as tool failure metadata
- **AND** rolls back the failed database transaction before continuing
- **AND** saves and returns the assistant response for the chat request

#### Scenario: Web evidence ingestion failure does not abort assistant response save

- **WHEN** trusted web fallback evidence is available but fallback evidence ingestion fails after database work has started
- **THEN** the assistant records the ingestion failure as tool failure metadata
- **AND** rolls back the failed database transaction before continuing
- **AND** saves and returns the assistant response for the chat request

### Requirement: Safety and failure handling

The assistant MUST resist prompt injection and MUST NOT claim a failed tool action was completed.

#### Scenario: Tool fails

- **WHEN** a tool call fails during a requested action
- **THEN** the assistant states that the action was not completed and logs the failure
