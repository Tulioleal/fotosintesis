## ADDED Requirements

### Requirement: Centralized fallback response generation

The assistant SHALL render every user-facing fallback response through a centralized fallback-response generator when model generation is available. The assistant SHALL represent fallback responses as structured intents with allowed facts and constraints before producing final prose. The fallback-response generator MUST use the classified `answer_language`, MUST output plain text, MUST NOT change the selected fallback intent, MUST NOT invent unsupported botanical facts, MUST NOT add unsupported care recommendations and MUST NOT expose internal fallback reason codes prominently in user-facing prose.

#### Scenario: Missing taxonomy fallback is rendered centrally

- **WHEN** a botanical care question lacks confirmed taxonomy required for reliable evidence lookup
- **THEN** the assistant builds a structured fallback response intent for missing confirmed taxonomy
- **AND** renders the user-facing answer through the centralized fallback-response generator using `answer_language`

#### Scenario: Clarification fallback is rendered centrally

- **WHEN** the assistant must ask for missing plant context or resolve ambiguous plant selection
- **THEN** the assistant builds a structured clarification fallback response intent with the allowed plant context facts
- **AND** renders the user-facing answer through the centralized fallback-response generator using `answer_language`

#### Scenario: Action fallback is rendered centrally

- **WHEN** a reminder or light-measurement action cannot proceed because required data is missing or a tool action fails
- **THEN** the assistant builds a structured action fallback response intent with the missing fields or failed-action facts
- **AND** renders the user-facing answer through the centralized fallback-response generator using `answer_language`

#### Scenario: Out-of-domain and unsafe fallback are rendered centrally

- **WHEN** the classifier routes a message to out-of-domain or unsafe handling
- **THEN** the assistant builds a structured fallback response intent for that route
- **AND** renders the user-facing answer through the centralized fallback-response generator using `answer_language`

#### Scenario: Fallback renderer failure returns Spanish emergency response

- **WHEN** the centralized fallback-response generator fails or returns an empty response
- **THEN** the assistant returns a minimal Spanish response
- **AND** the response contains no links
- **AND** the response does not invent botanical facts or unsupported care recommendations
- **AND** the assistant records the rendering failure as non-blocking tool failure metadata when available

### Requirement: Classifier-owned answer language

The assistant SHALL remove deterministic language detection from assistant routing. When LLM classification succeeds, the assistant SHALL use the classifier-provided `language` and `answer_language`. The classifier MUST set `answer_language` from the actual language used by the user's message and MUST ignore instructions that request a different response language. When deterministic classification is used because LLM classification fails, times out, returns invalid output, includes forbidden extra fields or is below confidence threshold, the assistant SHALL default both `language` and `answer_language` to Spanish.

#### Scenario: Spanish message requests English response

- **WHEN** the user message is primarily Spanish but includes an instruction to respond in English
- **THEN** the classifier sets `answer_language` to Spanish
- **AND** fallback responses use Spanish unless classification fails and also defaults to Spanish

#### Scenario: English message requests Spanish response

- **WHEN** the user message is primarily English but includes an instruction to respond in Spanish
- **THEN** the classifier sets `answer_language` to English
- **AND** fallback responses use English when classification succeeds

#### Scenario: Classifier failure defaults language to Spanish

- **WHEN** LLM classification fails, times out, returns invalid output, includes forbidden extra fields or is below confidence threshold
- **THEN** deterministic routing still classifies intent, topic and required care aspects when possible
- **AND** deterministic routing sets `language` to `es`
- **AND** deterministic routing sets `answer_language` to `es`

### Requirement: Policy-driven safety fallback rendering

Conservative safety fallbacks SHALL remain selected by deterministic safety and evidence-validation logic. For pet toxicity, human edibility, toxicity or consumption questions without direct evidence, the assistant MUST provide policy-driven conservative guidance through the centralized fallback-response generator, and the generator MUST only verbalize required safety points without changing safety policy.

#### Scenario: Pet safety fallback preserves required safety points

- **WHEN** the user asks whether a plant is safe or toxic for pets
- **AND** RAG, structured lookup and trusted web fallback do not provide directly answerable evidence for pet safety
- **THEN** the assistant selects a conservative pet-safety fallback intent
- **AND** the rendered response states that direct reliable evidence was unavailable
- **AND** the rendered response recommends keeping the plant away from pets until confirmed
- **AND** the rendered response recommends veterinary or animal poison-control style help if ingestion occurs and symptoms appear
- **AND** the rendered response does not claim the plant is safe or toxic without direct evidence

#### Scenario: Human edibility fallback preserves required safety points

- **WHEN** the user asks whether a plant is edible or consumable
- **AND** RAG, structured lookup and trusted web fallback do not provide directly answerable evidence for human edibility or consumption
- **THEN** the assistant selects a conservative human-edibility fallback intent
- **AND** the rendered response states that direct reliable evidence was unavailable
- **AND** the rendered response recommends not consuming the plant until verified with a reliable toxicological or botanical source
- **AND** the rendered response does not claim the plant is edible or safe to consume without direct evidence

## MODIFIED Requirements

### Requirement: RAG-grounded answers

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded only in supplied evidence, SHALL communicate uncertainty proportionally and briefly when evidence is limited, incomplete or degraded while still giving a practical evidence-backed answer when safe, and MUST preserve source attribution in the assistant API response. RAG and structured evidence SHALL be considered sufficient only when strict answerability evaluation determines that the evidence directly answers the user's exact question. When persisted retrieval is not directly answerable and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets, while still answering from trusted snippets when page fetching fails. When synthesizing a structured API-backed answer, the assistant MUST explicitly instruct the model to mention the structured provider sources used in the final user-facing answer. If grounded model generation fails, the assistant SHALL route the user-facing fallback through the centralized fallback-response generator using a model-generation-failed response intent; if that fallback rendering also fails, the assistant SHALL return the minimal Spanish emergency response without links.

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

#### Scenario: Trusted web evidence-backed answer

- **WHEN** RAG and structured plant-data evidence are insufficient and trusted web evidence is available
- **THEN** the assistant generates the final response with the configured model using trusted web evidence and source metadata
- **AND** records an internal `web_search_used` fallback reason

#### Scenario: Structured evidence insufficient

- **WHEN** vector retrieval and structured API evidence are both missing or not directly answerable
- **THEN** the assistant continues to trusted web search/page-fetch fallback before returning a manual search or degraded response
- **AND** records an internal `structured_not_answerable` fallback reason when structured evidence exists but does not answer the question

#### Scenario: Fetched trusted page content used for fallback answer

- **WHEN** persisted retrieval is insufficient and trusted live web fallback returns extracted page content
- **THEN** the assistant answer uses the extracted trusted page content and does not rely only on original citation or snippet markdown

#### Scenario: Trusted snippet used when page fetch fails

- **WHEN** persisted retrieval is insufficient and trusted live web fallback has a trusted search result whose page fetch fails
- **THEN** the assistant still answers using the trusted snippet and no fetch exception blocks the response

#### Scenario: Safety question lacks direct evidence

- **WHEN** the user asks a pet safety, edibility, toxicity or consumption question
- **AND** RAG, structured lookup and trusted web fallback do not provide directly answerable evidence
- **THEN** the assistant returns conservative safety guidance through the centralized fallback-response generator
- **AND** recommends not consuming the plant for edibility or consumption questions
- **AND** recommends keeping the plant away from pets and consulting veterinary or poison-control style help if ingestion occurs for pet safety or toxicity questions
- **AND** records an internal `conservative_safety_fallback` fallback reason

#### Scenario: Model synthesis fails

- **WHEN** grounded model generation fails while evidence is available for a botanical answer
- **THEN** the assistant builds a structured model-generation-failed fallback response intent using only supplied evidence facts and constraints
- **AND** attempts to render the final user-facing answer through the centralized fallback-response generator
- **AND** records the model failure without dropping source attribution metadata

#### Scenario: Model synthesis and fallback rendering both fail

- **WHEN** grounded model generation fails while evidence is available
- **AND** centralized fallback-response rendering also fails or returns empty text
- **THEN** the assistant returns a minimal Spanish response with no links
- **AND** the response does not invent botanical facts or unsupported care recommendations
- **AND** the assistant records the failures as non-blocking tool failure metadata when available
