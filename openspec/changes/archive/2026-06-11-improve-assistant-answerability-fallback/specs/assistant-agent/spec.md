## MODIFIED Requirements

### Requirement: LangGraph orchestration

The backend SHALL use LangGraph nodes for intent classification, user context loading, retrieval, strict answerability-based sufficiency evaluation, answer generation, clarification and failure handling.

#### Scenario: Evidence insufficient

- **WHEN** retrieval does not provide enough evidence that directly answers the user's exact botanical question
- **THEN** the graph routes to acquisition, clarification or limitation handling instead of inventing unsupported facts

#### Scenario: Retrieved chunks require answerability evaluation

- **WHEN** retrieval returns one or more chunks for a botanical question
- **THEN** the graph evaluates whether those chunks directly answer the user's exact question before marking retrieval sufficient

#### Scenario: Generic evidence rejected for specific question

- **WHEN** retrieval returns general care evidence for a plant
- **AND** the user asks a distinct question about pet safety, edibility, toxicity, native range, water temperature or another uncovered aspect
- **THEN** the graph treats the retrieved evidence as insufficient for that question

### Requirement: Tool-aware assistant

The assistant SHALL use tools for knowledge search, structured plant-data lookup, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup when appropriate. The assistant SHALL expose structured reminder suggestions for user confirmation when it proposes a reminder from conversation context instead of directly creating one. The assistant SHALL use structured plant-data lookup after non-answerable RAG evidence, and SHALL continue to trusted web search when structured plant-data evidence is also not directly answerable.

#### Scenario: Missing reminder data

- **WHEN** the user asks the assistant to create a reminder but plant, date, time or recurrence is missing
- **THEN** the assistant asks for the missing information before creating it

#### Scenario: Reminder suggestion requires confirmation

- **WHEN** the assistant proposes a reminder from conversation context and has plant, action, due date, due time and recurrence values
- **THEN** the assistant response includes an actionable reminder suggestion with the plant, action, due timestamp, recurrence and justification instead of relying only on message text

#### Scenario: Structured lookup follows insufficient RAG

- **WHEN** knowledge search returns evidence that is missing or not directly answerable for a botanical question with one confirmed scientific name
- **THEN** the assistant calls `plant_data_lookup` before `trusted_web_search`

#### Scenario: Structured lookup requires confirmed plant

- **WHEN** plant context is missing, ambiguous or unconfirmed
- **THEN** the assistant asks for clarification or confirmation instead of calling `plant_data_lookup`

#### Scenario: Structured evidence does not block web search unless answerable

- **WHEN** structured plant-data lookup returns evidence for a botanical question
- **AND** that structured evidence does not directly answer the user's exact question
- **THEN** the assistant continues to `trusted_web_search` instead of generating a structured answer from generic metadata

### Requirement: RAG-grounded answers

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded only in supplied evidence, SHALL communicate uncertainty proportionally and briefly when evidence is limited, incomplete or degraded while still giving a practical evidence-backed answer when safe, and MUST preserve source attribution in the assistant API response. RAG and structured evidence SHALL be considered sufficient only when strict answerability evaluation determines that the evidence directly answers the user's exact question. When persisted retrieval is not directly answerable and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets, while still answering from trusted snippets when page fetching fails. When synthesizing a structured API-backed answer, the assistant MUST explicitly instruct the model to mention the structured provider sources used in the final user-facing answer. If model generation fails, the assistant SHALL return a deterministic evidence summary and record the model failure as a non-blocking tool failure.

#### Scenario: Evidence-backed answer

- **WHEN** relevant documents are retrieved for a botanical question
- **AND** strict answerability evaluation determines those documents directly answer the user question
- **THEN** the assistant generates the final response with the configured model using those documents and avoids unsupported claims

#### Scenario: Retrieved evidence not answerable

- **WHEN** relevant documents are retrieved for a botanical question
- **AND** strict answerability evaluation determines those documents do not directly answer the user question
- **THEN** the assistant does not generate a RAG-only answer from those documents
- **AND** records an internal `rag_not_answerable` fallback reason

#### Scenario: Structured evidence-backed answer

- **WHEN** RAG evidence is insufficient and structured plant-data evidence is sufficient for a botanical question
- **AND** strict answerability evaluation determines the structured evidence directly answers the user question
- **THEN** the assistant generates the final response with the configured model using the structured evidence and provider metadata, and explicitly instructs the model to mention the structured provider sources used

#### Scenario: Structured evidence insufficient

- **WHEN** vector retrieval and structured API evidence are both missing or not directly answerable
- **THEN** the assistant continues to trusted web search/page-fetch fallback before returning a manual search or degraded response
- **AND** records an internal `structured_not_answerable` fallback reason when structured evidence exists but does not answer the question

#### Scenario: Trusted web evidence-backed answer

- **WHEN** RAG and structured plant-data evidence are insufficient and trusted web evidence is available
- **THEN** the assistant generates the final response with the configured model using trusted web evidence and source metadata
- **AND** records an internal `web_search_used` fallback reason

#### Scenario: Fetched trusted page content used for fallback answer

- **WHEN** persisted retrieval is insufficient and trusted live web fallback returns extracted page content
- **THEN** the assistant answer uses the extracted trusted page content and does not rely only on original citation or snippet markdown

#### Scenario: Trusted snippet used when page fetch fails

- **WHEN** persisted retrieval is insufficient and trusted live web fallback has a trusted search result whose page fetch fails
- **THEN** the assistant still answers using the trusted snippet and no fetch exception blocks the response

#### Scenario: Safety question lacks direct evidence

- **WHEN** the user asks a pet safety, edibility, toxicity or consumption question
- **AND** RAG, structured lookup and trusted web fallback do not provide directly answerable evidence
- **THEN** the assistant returns conservative safety guidance that states direct evidence was unavailable
- **AND** recommends not consuming the plant for edibility or consumption questions
- **AND** recommends keeping the plant away from pets and consulting veterinary or poison-control style help if ingestion occurs for pet safety or toxicity questions
- **AND** records an internal `conservative_safety_fallback` fallback reason

#### Scenario: Model synthesis fails

- **WHEN** model generation fails while evidence is available for a botanical answer
- **THEN** the assistant returns a deterministic summary from the available evidence and records the model failure without dropping source attribution

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted web search for botanical questions when retrieved RAG evidence is missing or not directly answerable and a specific plant context is available. The assistant SHALL also run trusted web search when structured plant-data evidence exists but is not directly answerable for the user's exact question.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning clarification or limitation text

#### Scenario: Non-answerable RAG triggers structured then web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns chunks that do not directly answer the question
- **THEN** the assistant attempts structured plant-data lookup before trusted web search
- **AND** calls trusted web search when structured plant-data evidence is missing or not directly answerable

#### Scenario: Web fallback answer uses live evidence

- **WHEN** trusted web search returns usable results after insufficient RAG evidence or non-answerable structured evidence
- **THEN** the assistant answers from the web result snippets or fetched page content, identifies the evidence as live web evidence, and avoids presenting it as reviewed persisted knowledge

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources for the web result URLs, titles, domains and confidence context

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted web search fails or returns no usable results after insufficient or non-answerable RAG and structured evidence
- **THEN** the assistant returns the existing degraded limitation or manual-search guidance instead of inventing unsupported botanical facts unless conservative safety fallback applies

## ADDED Requirements

### Requirement: Answerability decision tracking

The assistant SHALL track internal fallback reason codes for answerability and fallback routing decisions without making those internal codes prominent in the user-facing answer.

#### Scenario: RAG rejected by answerability

- **WHEN** retrieved RAG evidence is judged not directly answerable
- **THEN** the assistant records `rag_not_answerable` in internal response or debug metadata

#### Scenario: Structured evidence rejected by answerability

- **WHEN** structured evidence is judged not directly answerable
- **THEN** the assistant records `structured_not_answerable` in internal response or debug metadata

#### Scenario: Web search used

- **WHEN** trusted web search is invoked after non-answerable RAG or structured evidence
- **THEN** the assistant records `web_search_used` in internal response or debug metadata

#### Scenario: Conservative safety fallback used

- **WHEN** conservative safety fallback is returned
- **THEN** the assistant records `conservative_safety_fallback` in internal response or debug metadata
