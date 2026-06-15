## MODIFIED Requirements

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST NOT blend verified claims and general guidance in the same sentence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the judge result.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps

#### Scenario: Strong full-support non-safety answer accepted with lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the assistant treats the evidence as sufficient and answers from RAG without triggering web fallback

#### Scenario: Safety-sensitive aspect requires strict threshold

- **WHEN** a requested aspect is `pet_toxicity` or `human_edibility`
- **THEN** validation requires the aspect confidence to be above `assistant_safety_validation_threshold` (default 0.85) before marking the aspect covered

#### Scenario: Partial non-critical coverage answers covered aspects

- **WHEN** validated evidence covers at least one requested non-critical required aspect but leaves other non-critical aspects missing
- **THEN** the assistant answers the source-supported parts
- **AND** briefly states which requested aspects could not be source-validated
- **AND** any conservative general guidance for missing aspects is clearly labeled as general and not validated for the specific plant/question

#### Scenario: No validated coverage returns transparent insufficient answer

- **WHEN** no requested required aspects are covered by validated evidence
- **THEN** the assistant states that source-backed evidence was insufficient for the specific plant/question
- **AND** any conservative general guidance is clearly labeled as general and not source-validated for the specific plant/question
- **AND** the assistant does not cite general guidance as source-backed evidence

#### Scenario: Safety-sensitive missing evidence returns conservative guidance

- **WHEN** a safety-sensitive care question lacks direct validated evidence for the primary safety aspect at the configured safety-sensitive threshold
- **THEN** the assistant states that direct source-backed evidence was unavailable for the specific plant/question
- **AND** the assistant may provide conservative safety guidance labeled as general and not source-validated
- **AND** the assistant does not claim the plant is safe, toxic, edible, or consumable without direct evidence

#### Scenario: Contradictory evidence is presented without definitive claim

- **WHEN** final evidence validation reports contradictory source-supported claims for a requested aspect
- **THEN** the assistant states that the sources conflict
- **AND** the assistant shows source links in the text for the conflicting claims
- **AND** the assistant avoids a definitive recommendation from the contradictory evidence

### Requirement: RAG-grounded answers

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded in supplied source-supported evidence for verified claims, SHALL communicate uncertainty proportionally when evidence is limited, incomplete or contradictory, and MUST preserve source attribution in the assistant API response. RAG evidence SHALL be considered full only when answerability evaluation determines that it directly answers every requested required aspect. When RAG is structurally strong and meets the strong-answer threshold, the assistant SHALL NOT trigger web fallback. When persisted retrieval is not full and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets while still answering from trusted snippets when page fetching fails. If grounded model generation fails, the assistant SHALL route the user-facing fallback through the centralized fallback-response generator using a model-generation-failed response intent; if that fallback rendering also fails, the assistant SHALL return the minimal Spanish emergency response without links.

#### Scenario: Strong RAG answer accepted without web fallback

- **WHEN** RAG evidence is structurally strong (status full, answerable, all aspects covered, source support present, no contradictions) and confidence is above `assistant_strong_answer_validation_threshold`
- **AND** no requested aspect is safety-sensitive
- **THEN** the assistant answers from RAG evidence without calling trusted web search
- **AND** the response metadata does not include `web_search_used` in fallback reasons

#### Scenario: Evidence-backed answer

- **WHEN** relevant documents are retrieved for a botanical question
- **AND** strict answerability evaluation determines those documents fully answer the user question
- **THEN** the assistant generates the final response with the configured model using those documents and avoids unsupported claims

#### Scenario: Retrieved evidence not full

- **WHEN** relevant documents are retrieved for a botanical question
- **AND** answerability evaluation determines those documents are `partial`, `insufficient`, or `contradictory`
- **THEN** the assistant does not generate a RAG-only final answer from those documents
- **AND** records an internal RAG answerability status for routing and diagnostics

#### Scenario: Trusted web evidence-backed answer

- **WHEN** RAG evidence is not full and trusted web evidence is available
- **THEN** the assistant runs a final combined judge over RAG and web evidence
- **AND** generates the final response with the configured model using only final-judge-supported source claims for verified statements
- **AND** records an internal `web_search_used` fallback reason

#### Scenario: Fetched trusted page content used for fallback answer

- **WHEN** persisted retrieval is not full and trusted live web fallback returns extracted page content
- **THEN** the assistant answer uses the extracted trusted page content when the final combined judge supports claims from that content
- **AND** the assistant does not rely only on original citation or snippet markdown for those supported claims

#### Scenario: Trusted snippet used when page fetch fails

- **WHEN** persisted retrieval is not full and trusted web fallback has a trusted search result whose page fetch fails
- **THEN** the assistant may answer using the trusted snippet if the final combined judge validates the snippet for a requested aspect
- **AND** no fetch exception blocks the response

#### Scenario: Safety question lacks direct evidence

- **WHEN** the user asks a pet safety, edibility, toxicity or consumption question
- **AND** final combined judging does not provide direct source-supported evidence for the safety aspect
- **THEN** the assistant returns conservative safety guidance labeled as general and not source-validated for the specific plant/question
- **AND** recommends not consuming the plant for edibility or consumption questions
- **AND** recommends keeping the plant away from pets and consulting veterinary or poison-control style help if ingestion occurs for pet safety or toxicity questions
- **AND** records an internal `conservative_safety_fallback` fallback reason

#### Scenario: Contradictory trusted evidence

- **WHEN** final combined judging reports contradictory source-supported evidence
- **THEN** the assistant presents the conflict with source links
- **AND** does not choose one claim as definitive unless the final judge resolves the contradiction as full or partial with clear support

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

### Requirement: Answerability decision tracking

The assistant SHALL track internal fallback reason codes and answerability statuses for routing decisions without making internal codes prominent in the user-facing answer.

#### Scenario: RAG rejected by answerability

- **WHEN** retrieved RAG evidence is judged not full
- **THEN** the assistant records the RAG answerability status and `rag_not_answerable` or equivalent internal routing metadata

#### Scenario: RAG accepted by strong threshold

- **WHEN** retrieved RAG evidence is structurally strong and meets the strong-answer threshold
- **THEN** the assistant records the RAG answerability status without `rag_not_answerable` or `web_search_used` fallback reasons

#### Scenario: Structured lookup skipped

- **WHEN** RAG evidence is not full in the normal chat-time plant-care answer path
- **THEN** the assistant records routing metadata without recording a failed structured lookup attempt
- **AND** no `plant_data_lookup` call is required before web search

#### Scenario: Web search used

- **WHEN** trusted web search is invoked after non-full RAG evidence
- **THEN** the assistant records `web_search_used` in internal response or debug metadata

#### Scenario: Conservative safety fallback used

- **WHEN** conservative safety guidance is returned because direct validated evidence is unavailable
- **THEN** the assistant records `conservative_safety_fallback` in internal response or debug metadata

#### Scenario: Contradictory status tracked

- **WHEN** final combined judging reports contradictory evidence
- **THEN** the assistant records the contradictory status, affected aspects, and source URLs in bounded diagnostic metadata

### Requirement: Tool-aware assistant

The assistant SHALL use tools for knowledge search, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup when appropriate. The assistant SHALL expose structured reminder suggestions for user confirmation when it proposes a reminder from conversation context instead of directly creating one. The assistant SHALL not call structured plant-data lookup in the normal chat-time plant-care answer path after non-full RAG evidence. The assistant SHALL enforce configurable timeouts on answerability judge and web search tool calls.

#### Scenario: Judge timeout returns controlled result

- **WHEN** the answerability judge exceeds `assistant_judge_timeout_seconds`
- **THEN** the assistant returns a controlled `AnswerabilityResult` with `status: "insufficient"` and reason containing "timed out"
- **AND** the request does not hang

#### Scenario: Web search timeout returns controlled fallback

- **WHEN** the trusted web search exceeds `assistant_web_search_timeout_seconds`
- **THEN** the assistant records a tool failure with "timed out" reason
- **AND** the request completes with fallback reasons preserved

#### Scenario: Missing reminder data

- **WHEN** the user asks the assistant to create a reminder but plant, date, time or recurrence is missing
- **THEN** the assistant asks for the missing information before creating it

#### Scenario: Reminder suggestion requires confirmation

- **WHEN** the assistant proposes a reminder from conversation context and has plant, action, due date, due time and recurrence values
- **THEN** the assistant response includes an actionable reminder suggestion with the plant, action, due timestamp, recurrence and justification instead of relying only on message text

#### Scenario: Structured lookup skipped after non-full RAG

- **WHEN** knowledge search returns evidence that is missing, partial, insufficient, or contradictory for a botanical question with one confirmed scientific name
- **THEN** the assistant calls trusted web search before final answer generation
- **AND** the assistant does not call `plant_data_lookup` in the normal chat-time plant-care answer path

#### Scenario: Structured lookup requires confirmed plant

- **WHEN** plant context is missing, ambiguous or unconfirmed
- **THEN** the assistant asks for clarification or confirmation instead of calling `plant_data_lookup`

#### Scenario: Structured providers remain outside chat-time path

- **WHEN** Trefle or Perenual services are configured in the backend
- **THEN** normal plant-care chat answer generation does not block on those providers
- **AND** those providers remain available for non-chat-time or future offline ingestion flows
