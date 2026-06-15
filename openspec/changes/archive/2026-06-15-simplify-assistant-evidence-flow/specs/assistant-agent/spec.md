## MODIFIED Requirements

### Requirement: LangGraph orchestration

The backend SHALL use LangGraph nodes for intent classification, user context loading, enriched RAG retrieval, explicit answerability evaluation, live web fallback when RAG is not full, final combined evidence judging, answer generation, clarification and failure handling.

#### Scenario: RAG evidence insufficient

- **WHEN** retrieval does not provide evidence that fully answers the user's exact botanical question
- **THEN** the graph routes to live web search before producing the final plant-care answer
- **AND** the graph does not route to structured plant-data lookup in the normal chat-time plant-care answer path

#### Scenario: Retrieved chunks require answerability evaluation

- **WHEN** retrieval returns one or more chunks for a botanical question
- **THEN** the graph evaluates whether those chunks answer the user's exact question before marking retrieval full
- **AND** the evaluation result includes `full`, `partial`, `insufficient`, or `contradictory` status

#### Scenario: Generic evidence rejected for specific question

- **WHEN** retrieval returns general care evidence for a plant
- **AND** the user asks a distinct question about pet safety, edibility, toxicity, native range, water temperature or another uncovered aspect
- **THEN** the graph treats the retrieved evidence as not full for that question
- **AND** the graph searches live web evidence before final answer generation

#### Scenario: RAG full answers directly

- **WHEN** RAG evidence fully covers all requested required aspects for the exact user question
- **THEN** the graph generates the answer from RAG evidence without calling trusted web search or structured plant-data lookup

#### Scenario: RAG partial searches web

- **WHEN** RAG evidence covers only some requested required aspects
- **THEN** the graph searches live web evidence before final answer generation
- **AND** the final combined judge may upgrade, preserve, or downgrade the answerability status

#### Scenario: RAG contradictory searches web

- **WHEN** RAG evidence contains contradictions for requested required aspects
- **THEN** the graph searches live web evidence before final answer generation
- **AND** the final answer does not make definitive recommendations from contradictory evidence

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST NOT blend verified claims and general guidance in the same sentence.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps

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

### Requirement: Tool-aware assistant

The assistant SHALL use tools for knowledge search, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup when appropriate. The assistant SHALL expose structured reminder suggestions for user confirmation when it proposes a reminder from conversation context instead of directly creating one. The assistant SHALL not call structured plant-data lookup in the normal chat-time plant-care answer path after non-full RAG evidence.

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

### Requirement: RAG-grounded answers

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded in supplied source-supported evidence for verified claims, SHALL communicate uncertainty proportionally when evidence is limited, incomplete or contradictory, and MUST preserve source attribution in the assistant API response. RAG evidence SHALL be considered full only when answerability evaluation determines that it directly answers every requested required aspect. When persisted retrieval is not full and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets while still answering from trusted snippets when page fetching fails. If grounded model generation fails, the assistant SHALL route the user-facing fallback through the centralized fallback-response generator using a model-generation-failed response intent; if that fallback rendering also fails, the assistant SHALL return the minimal Spanish emergency response without links.

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

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted-first web search for botanical questions when retrieved RAG evidence is partial, insufficient, contradictory, missing, or degraded and a specific confirmed plant context is available. The assistant SHALL construct trusted web fallback queries from the operational scientific name, classified topic, requested required aspects, a capped copy of the original user question, and trusted botanical source terms. One web search call MAY yield multiple candidate source URLs; the assistant SHALL fetch up to three usable sources and SHALL run one final combined judge over RAG and web evidence before answer synthesis. The assistant MUST validate final judge output structurally before using source support for answer synthesis, response source attribution, or background ingestion.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has confirmed plant context and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning final answer text

#### Scenario: Non-full RAG triggers web fallback

- **WHEN** a botanical question has confirmed plant context and RAG evaluation returns `partial`, `insufficient`, or `contradictory`
- **THEN** the assistant calls trusted web search before final answer generation
- **AND** the assistant does not call structured plant-data lookup in the normal chat-time path

#### Scenario: Unsupported botanical question terms are preserved in web query

- **WHEN** RAG evidence is not full for a botanical question whose intent is not represented by the classified topic alone
- **THEN** the trusted web search query includes the operational scientific name, required aspects, and relevant terms from the original user question
- **AND** the trusted web search query uses capped question context rather than only the generic classified topic

#### Scenario: Allowed-domain web results take precedence

- **WHEN** trusted web search returns one or more results whose source domains are in the allowed trusted-domain set
- **THEN** the assistant uses only those allowed-domain results as candidate fallback answer evidence
- **AND** the assistant ignores external results from the same search response

#### Scenario: Single external fallback result allowed

- **WHEN** trusted web search returns zero results whose source domains are in the allowed trusted-domain set
- **AND** trusted web search returns one or more external results
- **THEN** the assistant selects at most one external result as fallback answer evidence

#### Scenario: Up to three web sources are fetched

- **WHEN** one trusted web search call returns multiple selected source URLs
- **THEN** the assistant fetches no more than three usable sources for the final combined judge
- **AND** page fetch failures degrade to available snippets without blocking the answer

#### Scenario: Web fallback answer uses final judged evidence

- **WHEN** trusted-first web search returns usable allowed-domain or external fallback results after non-full RAG evidence
- **THEN** the assistant runs one final combined judge over RAG chunks, RAG judge output, and selected web evidence
- **AND** answers verified claims only from final judge `source_support`
- **AND** identifies live web evidence in sources or metadata according to current response conventions

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources only for URLs that the final combined judge supports or identifies in contradictions

#### Scenario: Trusted page fetch failure does not trigger external fallback

- **WHEN** trusted web search returns one or more allowed-domain results
- **AND** page fetching fails or extraction yields no usable page content for those results
- **THEN** the assistant does not select external fallback results for that search attempt
- **AND** existing snippet degradation or limitation behavior applies

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted-first web search fails or returns no usable selected results after non-full RAG evidence
- **THEN** the assistant returns a transparent insufficient or conservative answer according to final evidence status
- **AND** the assistant does not invent source-backed botanical facts

#### Scenario: Off-aspect source excluded from verified claims

- **WHEN** trusted web fallback returns one source that supports a requested watering aspect and another source that covers no requested aspect
- **THEN** the final combined judge excludes the off-aspect source from `source_support`
- **AND** the assistant does not cite the off-aspect source for verified answer claims

#### Scenario: Partial web validation leaves missing aspects unresolved

- **WHEN** final combined judging supports only one of multiple requested missing non-critical aspects
- **THEN** the assistant treats that evidence as verified only for the covered aspect
- **AND** the assistant keeps the remaining requested aspects missing for partial or insufficient answer handling

#### Scenario: Safety-sensitive web evidence requires direct support

- **WHEN** the requested missing aspect is pet toxicity, human edibility or another safety-sensitive aspect
- **THEN** final combined judging must report direct source support and meet the safety validation threshold before the assistant treats the aspect as verified
- **AND** the assistant returns conservative general guidance when no direct source support validates the safety-sensitive aspect

### Requirement: Answerability decision tracking

The assistant SHALL track internal fallback reason codes and answerability statuses for routing decisions without making internal codes prominent in the user-facing answer.

#### Scenario: RAG rejected by answerability

- **WHEN** retrieved RAG evidence is judged not full
- **THEN** the assistant records the RAG answerability status and `rag_not_answerable` or equivalent internal routing metadata

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

## ADDED Requirements

### Requirement: Explicit answerability result contract

The assistant plant-care evidence pipeline SHALL represent answerability with a structured result containing `status`, compatibility `answerable`, `covered_aspects`, `missing_aspects`, `source_support`, `contradictions`, `reason`, and `confidence`.

#### Scenario: Full result is structurally valid

- **WHEN** an answerability result has `status: "full"`
- **THEN** `covered_aspects` includes all requested required aspects
- **AND** `source_support` is not empty
- **AND** `answerable` remains true for compatibility

#### Scenario: Partial result is structurally valid

- **WHEN** an answerability result has `status: "partial"`
- **THEN** `covered_aspects` is not empty
- **AND** `missing_aspects` identifies uncovered requested required aspects
- **AND** `answerable` remains false unless compatibility code explicitly treats partial as answerable for covered aspects only

#### Scenario: Insufficient result is structurally valid

- **WHEN** an answerability result has `status: "insufficient"`
- **THEN** the result is not used for source-supported claim persistence
- **AND** `answerable` is false

#### Scenario: Contradictory result requires source URLs

- **WHEN** an answerability result has `status: "contradictory"`
- **THEN** `contradictions` includes source URLs for the conflicting claims
- **AND** the result is not used for source-supported claim persistence

#### Scenario: Incoherent judge output degrades safely

- **WHEN** judge output is missing fields required by its declared status
- **THEN** the assistant degrades the status to `partial` or `insufficient` according to available source support
- **AND** the assistant does not persist evidence from the incoherent result

### Requirement: Post-response validated claim ingestion scheduling

The assistant SHALL schedule validated web-claim ingestion from `AssistantService.chat` after the user-facing response is prepared and conversation persistence is not dependent on the ingestion transaction.

#### Scenario: Background ingestion uses dedicated session

- **WHEN** the assistant schedules ingestion for final judge source-supported claims
- **THEN** the background task opens its own database session via `AsyncSessionLocal`
- **AND** it does not reuse the request-scoped session from the chat request

#### Scenario: Background ingestion receives serializable payload

- **WHEN** `AssistantService.chat` schedules background ingestion
- **THEN** it passes only serializable validated claim, source, taxonomy, topic, aspect, confidence and context metadata
- **AND** it does not pass live ORM objects or graph state objects requiring an open request session

#### Scenario: Background ingestion failure is explicit

- **WHEN** background ingestion, embedding or indexing fails
- **THEN** the task rolls back its own transaction
- **AND** logs the exception with conversation, plant, source and answerability context when available
- **AND** the already-prepared user response is not blocked or invalidated

#### Scenario: Only source-supported claims are scheduled

- **WHEN** final answerability status is `full` or safe `partial` with `source_support`
- **THEN** the assistant schedules ingestion only for source-supported claims from the final judge
- **AND** it does not schedule final assistant response text, full pages by default, general guidance, insufficient evidence, contradictory evidence, or unsupported claims

### Requirement: Taxonomy topic mapping

The assistant classifier and retrieval pipeline SHALL support a taxonomy care topic for native-range and taxonomy-oriented plant-care questions.

#### Scenario: Native range maps to taxonomy topic

- **WHEN** classification identifies `native_range` as a required aspect
- **THEN** the classified topic maps to `taxonomy`
- **AND** retrieval still includes required aspects and the original user question instead of relying only on topic
