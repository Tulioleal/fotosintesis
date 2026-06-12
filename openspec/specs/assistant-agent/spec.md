## Purpose

TBD - Defines the assistant-agent capability for plant-care chat, orchestration, tools, grounded answers, and safe failure handling.

## Requirements

### Requirement: Chat experience

The system SHALL provide a chat API and frontend conversation UI for a plant-care assistant.

#### Scenario: User sends botanical question

- **WHEN** a user sends a supported plant-care question
- **THEN** the system creates or continues a conversation and returns an assistant response

### Requirement: Separated plant taxonomy context

The assistant chat flow SHALL accept separated plant display, binomial and scientific-name context from the frontend while preserving support for existing requests that only provide a plant string.

#### Scenario: Chat request includes binomial and scientific context

- **WHEN** the assistant page is opened with `plant`, `binomial` and `scientific` query parameters
- **THEN** the frontend sends `plant`, `plant_binomial_name` and `plant_scientific_name` in the assistant chat request

#### Scenario: Binomial context preferred for plant operations

- **WHEN** an assistant chat request includes `plant_binomial_name`
- **THEN** the assistant uses the binomial name as the preferred plant context for botanical search, structured lookup and retrieval operations

#### Scenario: Plant-only chat remains compatible

- **WHEN** the assistant page or request only provides `plant`
- **THEN** the chat flow continues to send and process the request without requiring binomial or scientific-name fields

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

### Requirement: Multilingual care intent classification

The assistant plant-care answer pipeline SHALL classify user input before retrieval using a closed multilingual classifier contract that includes `language`, `answer_language`, `intent`, `topic`, `required_aspects`, `plant_reference`, `confidence`, and `needs_retrieval`. The classifier SHALL use the configured cheaper/faster model from the same provider family as the main answer model. Classifier output MUST pass schema validation and meet the configured classification acceptance threshold before it can drive retrieval.

#### Scenario: Spanish watering frequency classification

- **WHEN** a user asks a Spanish plant-care question about how often to water a confirmed plant
- **THEN** the classifier output uses `intent: "plant_care_question"`, `topic: "watering"`, includes `watering_frequency_or_trigger` in `required_aspects`, sets `answer_language` to Spanish, and marks retrieval as needed

#### Scenario: Italian watering frequency classification

- **WHEN** a user asks an Italian plant-care question about watering frequency for a confirmed plant
- **THEN** the classifier output maps the question to the canonical `watering_frequency_or_trigger` required aspect and preserves Italian as the answer language

#### Scenario: Multi-aspect classification

- **WHEN** a user asks one plant-care question covering watering and light
- **THEN** the classifier output includes all applicable canonical required aspects for the requested watering and light information

#### Scenario: Non-care intent routes away from care retrieval

- **WHEN** the classifier returns `garden_action`, `reminder_request`, `light_measurement_question`, `plant_identification_question`, `out_of_domain`, or `unsafe_or_injection`
- **THEN** the assistant routes according to the non-care intent and does not run the plant-care evidence retrieval pipeline

### Requirement: Classifier fallback handling

The assistant SHALL fall back to deterministic classification or clarification when the multilingual classifier fails, times out, returns invalid JSON, returns unknown enum values, or returns confidence below the configured acceptance threshold. The fallback path SHALL NOT treat unvalidated classifier output as authoritative.

#### Scenario: Invalid classifier output

- **WHEN** the classifier returns invalid JSON or values outside the allowed intent, topic, or required-aspect sets
- **THEN** the assistant ignores the classifier output and uses deterministic routing or asks for clarification

#### Scenario: Low-confidence classifier output

- **WHEN** the classifier confidence is lower than the configured classification acceptance threshold
- **THEN** the assistant uses deterministic routing or asks for clarification before any care-answer retrieval is attempted

#### Scenario: Classifier provider failure

- **WHEN** the classifier provider fails or times out
- **THEN** the assistant records the failure through existing failure metadata and continues with deterministic routing or clarification

### Requirement: Confirmed taxonomy gate for care answers

The assistant plant-care answer pipeline MUST use confirmed taxonomic context for retrieval, structured lookup, trusted web search, embeddings, and indexing. It SHALL prefer `plant_binomial_name`, SHALL fall back only to `plant_scientific_name`, and MUST NOT use nickname, apodo, display name, or `plant_reference` for evidence operations. Display names MAY be preserved for user-facing answer wording.

#### Scenario: Binomial taxonomy used for care retrieval

- **WHEN** a plant-care answer request includes `plant`, `plant_binomial_name`, and `plant_scientific_name`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `plant_binomial_name` as the operational taxonomy
- **AND** the user-facing answer may still refer to the display plant name

#### Scenario: Scientific taxonomy fallback used for care retrieval

- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `plant_scientific_name` as the operational taxonomy

#### Scenario: Display name is not used for care evidence operations

- **WHEN** a plant-care answer request includes only a nickname, apodo, display name, or classifier `plant_reference` without confirmed taxonomy
- **THEN** the assistant does not run retrieval, structured lookup, trusted web search, embeddings, or indexing with that name
- **AND** it asks for clarification or reports the inconsistent missing-taxonomy state

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

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested `required_aspects` before synthesizing a plant-care answer. Final care answers MUST include only claims supported by validated evidence and SHALL preserve the classified `answer_language`.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps

#### Scenario: Partial non-critical coverage answers only covered aspects

- **WHEN** validated evidence covers at least one requested non-critical required aspect but leaves other non-critical aspects missing
- **THEN** the assistant answers only the covered aspects and briefly states which requested aspects could not be validated

#### Scenario: No validated coverage returns fallback

- **WHEN** no requested required aspects are covered by validated evidence
- **THEN** the assistant returns a clear fallback explaining that it lacks validated evidence and does not fabricate care advice

#### Scenario: Safety-sensitive missing evidence returns conservative fallback

- **WHEN** a safety-sensitive care question lacks direct validated evidence for the primary safety aspect at the configured safety-sensitive threshold
- **THEN** the assistant refuses unsafe partial advice and returns a conservative safety fallback

### Requirement: Care answer diagnostic metadata

The assistant response SHALL expose bounded diagnostic metadata for plant-care answers including `intent`, `topic`, `required_aspects`, `covered_aspects`, `missing_aspects`, `evidence_path`, and `answer_language`. The response MUST NOT expose prompts, raw model reasoning, raw full evidence text, or internal provider errors beyond existing tool failure metadata.

#### Scenario: Diagnostics included for grounded answer

- **WHEN** the assistant returns a plant-care answer from validated evidence
- **THEN** the response metadata includes intent, topic, requested aspects, covered aspects, missing aspects, evidence path, and answer language

#### Scenario: Internal details are not exposed

- **WHEN** the assistant response includes diagnostic metadata
- **THEN** the metadata excludes prompts, raw model reasoning, raw full evidence text, and provider internals except existing tool failure summaries

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

The assistant SHALL run trusted-first web search for botanical questions when retrieved RAG evidence is missing or not directly answerable and a specific plant context is available. The assistant SHALL also run trusted web search when structured plant-data evidence exists but is not directly answerable for the user's exact question. The assistant SHALL use allowed-domain search results exclusively when any are returned, and SHALL select at most one external fallback result only when no allowed-domain search results are returned. The assistant SHALL construct trusted web fallback queries from the operational scientific name, a capped copy of the original user question, and trusted botanical source terms so unsupported botanical question intent is preserved. The assistant MUST validate each selected fallback source independently against the requested missing care aspects before using that source for answer synthesis or response source attribution.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning clarification or limitation text

#### Scenario: Non-answerable RAG triggers structured then web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns chunks that do not directly answer the question
- **THEN** the assistant attempts structured plant-data lookup before trusted web search
- **AND** calls trusted web search when structured plant-data evidence is missing or not directly answerable

#### Scenario: Unsupported botanical question terms are preserved in web query

- **WHEN** RAG and structured plant-data evidence are insufficient for a botanical question whose intent is not represented by the classified topic
- **THEN** the trusted web search query includes the operational scientific name and the relevant terms from the original user question
- **AND** the trusted web search query uses capped question context rather than only the generic classified topic

#### Scenario: Allowed-domain web results take precedence

- **WHEN** trusted web search returns one or more results whose source domains are in the allowed trusted-domain set
- **THEN** the assistant uses only those allowed-domain results for fallback answer evidence
- **AND** the assistant ignores external results from the same search response

#### Scenario: Single external fallback result allowed

- **WHEN** trusted web search returns zero results whose source domains are in the allowed trusted-domain set
- **AND** trusted web search returns one or more external results
- **THEN** the assistant selects at most one external result as fallback answer evidence

#### Scenario: Web fallback answer uses live evidence

- **WHEN** trusted-first web search returns usable allowed-domain or external fallback results after insufficient RAG evidence or non-answerable structured evidence
- **THEN** the assistant validates each usable fallback source independently against the requested missing aspects before answer generation
- **AND** answers only from independently validated source snippets or fetched page content
- **AND** identifies the evidence as live web evidence and avoids presenting it as reviewed persisted knowledge

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources only for independently validated web result URLs, titles, domains and confidence context

#### Scenario: Trusted page fetch failure does not trigger external fallback

- **WHEN** trusted web search returns one or more allowed-domain results
- **AND** page fetching fails or extraction yields no usable page content for those results
- **THEN** the assistant does not select external fallback results for that search attempt
- **AND** existing snippet degradation or limitation behavior applies

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted-first web search fails or returns no usable selected results after insufficient or non-answerable RAG and structured evidence
- **THEN** the assistant returns the existing degraded limitation or manual-search guidance instead of inventing unsupported botanical facts unless conservative safety fallback applies

#### Scenario: Off-aspect trusted source excluded from prompt and response sources

- **WHEN** trusted web fallback returns one source that independently validates for a requested watering aspect and another trusted source that covers no requested missing aspect
- **THEN** the assistant includes only the validated watering source in the answer synthesis prompt
- **AND** the assistant response source metadata includes only the validated watering source

#### Scenario: Partial web validation leaves missing aspects unresolved

- **WHEN** a web fallback source independently validates for only one of multiple requested missing non-critical aspects
- **THEN** the assistant treats that source as evidence only for the validated aspect
- **AND** the assistant keeps the remaining requested aspects missing for partial-answer or limitation handling

#### Scenario: Safety-sensitive web source must validate independently

- **WHEN** the requested missing aspect is pet toxicity, human edibility or another safety-sensitive aspect
- **THEN** each web source must independently satisfy direct-evidence checks and the safety validation threshold before the assistant uses that source
- **AND** the assistant returns conservative safety guidance when no source independently validates for the safety-sensitive aspect

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

### Requirement: Web fallback failures are tracked without blocking answers

The assistant MUST record trusted web-search or fallback persistence failures in tool failure metadata while still returning an answer when usable web evidence is available. The assistant MUST preserve fallback route metadata for attempted trusted web search even when the search tool fails before returning usable evidence.

#### Scenario: Search fails before fallback answer

- **WHEN** trusted web search fails and no sufficient RAG evidence exists
- **THEN** the assistant records the search failure and returns limitation or manual-search guidance
- **AND** the assistant response metadata includes the `web_search_used` fallback reason

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

### Requirement: Assistant plant naming context

The assistant chat API SHALL accept optional `plant_binomial_name` and `plant_scientific_name` fields in addition to the existing optional `plant` field, and SHALL derive separate operational and display/context plant names from those fields.

#### Scenario: Binomial name is used for operations

- **WHEN** an assistant chat request includes `plant`, `plant_binomial_name`, and `plant_scientific_name`
- **THEN** the assistant uses `plant_binomial_name` as the operational plant name for retrieval, search, API, and acquisition tool calls
- **AND** preserves `plant_scientific_name` as taxonomic context

#### Scenario: Scientific name is operational fallback

- **WHEN** an assistant chat request omits `plant_binomial_name` and includes `plant_scientific_name`
- **THEN** the assistant uses `plant_scientific_name` as the operational plant name

#### Scenario: Legacy plant field remains supported

- **WHEN** an assistant chat request includes only `plant` for plant context
- **THEN** the assistant uses `plant` as both the operational plant name and display/context plant name

#### Scenario: Display context prefers plant label

- **WHEN** an assistant chat request includes `plant` and a different `plant_binomial_name`
- **THEN** the assistant presents `plant` as the primary selected plant context in user-facing chat context
- **AND** may include the binomial name as concise secondary context

### Requirement: Assistant entry URL taxonomy context

The frontend assistant page SHALL read `plant`, `binomial`, and `scientific` query parameters and send them to the assistant chat API as `plant`, `plant_binomial_name`, and `plant_scientific_name` respectively.

#### Scenario: Assistant route maps query parameters to payload

- **WHEN** the assistant page is opened with `plant`, `binomial`, and `scientific` query parameters and the user sends a message
- **THEN** the chat request payload includes the display plant, binomial plant name, and full scientific plant name in the corresponding backend fields

#### Scenario: Assistant UI shows concise context

- **WHEN** both display plant and binomial name are available on the assistant page
- **THEN** the assistant UI shows the display plant as the initial context and the binomial name as secondary context
- **AND** does not show a more verbose full scientific name by default when the binomial name is present

#### Scenario: Identification entry passes taxonomy names

- **WHEN** a user opens the assistant from an identification result with common, binomial, and accepted or suggested scientific names
- **THEN** the assistant link uses the common name when available as `plant`, the binomial name as `binomial`, and the accepted or suggested scientific name as `scientific`

#### Scenario: Garden profile entry passes available binomial context

- **WHEN** a user opens the assistant from a garden or plant profile view that exposes both `binomial_name` and `scientific_name`
- **THEN** the assistant link includes both `binomial` and `scientific` query parameters

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
