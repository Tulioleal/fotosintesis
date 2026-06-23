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

The backend SHALL use LangGraph nodes for intent classification, user context loading, enriched RAG retrieval, explicit answerability evaluation, live web fallback when RAG is not full, final combined evidence judging, answer generation, clarification and failure handling.

#### Scenario: RAG evidence insufficient

- **WHEN** retrieval does not provide enough evidence that directly answers the user's exact botanical question
- **THEN** the graph routes to live web search before producing the final plant-care answer
- **AND** the graph does not route to structured plant-data lookup in the normal chat-time plant-care answer path

#### Scenario: Retrieved chunks require answerability evaluation

- **WHEN** retrieval returns one or more chunks for a botanical question
- **THEN** the graph evaluates whether those chunks directly answer the user's exact question before marking retrieval sufficient
- **AND** the evaluation result includes `full`, `partial`, `insufficient`, or `contradictory` status

#### Scenario: Generic evidence rejected for specific question

- **WHEN** retrieval returns general care evidence for a plant
- **AND** the user asks a distinct question about pet safety, edibility, toxicity, native range, water temperature or another uncovered aspect
- **THEN** the graph treats the retrieved evidence as insufficient for that question
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

### Requirement: Multilingual care intent classification

The assistant plant-care answer pipeline SHALL classify user input before retrieval using a closed multilingual classifier contract that includes `language`, `answer_language`, `intent`, `topic`, `required_aspects`, `plant_reference`, `confidence`, and `needs_retrieval`. The classifier SHALL use the configured cheaper/faster model from the same provider family as the main answer model. Classifier output MUST pass schema validation before it can drive routing or retrieval. Classifier confidence SHALL be retained as observability metadata and SHALL NOT be the sole reason to reject an otherwise valid classifier output.

#### Scenario: Spanish watering frequency classification

- **WHEN** a user asks a Spanish plant-care question about how often to water a confirmed plant
- **THEN** the classifier output uses `intent: "plant_care_question"`, `topic: "watering"`, includes `watering_frequency_or_trigger` in `required_aspects`, sets `answer_language` to Spanish, and marks retrieval as needed

#### Scenario: Italian watering frequency classification

- **WHEN** a user asks an Italian plant-care question about watering frequency for a confirmed plant
- **THEN** the classifier output maps the question to the canonical `watering_frequency_or_trigger` required aspect and preserves Italian as the answer language

#### Scenario: Multi-aspect classification

- **WHEN** a user asks one plant-care question covering watering and light
- **THEN** the classifier output includes only the applicable domain-qualified watering and light required aspects directly requested by the message

#### Scenario: Symptom diagnosis classification

- **WHEN** a user asks what yellow leaves, browning, leaf drop, wilting, spots, lesions, mushy tissue, or stunted growth could mean without explicitly asking about a specific care routine
- **THEN** the classifier uses `topic: "diagnosis"`
- **AND** required aspects use matching `diagnosis_*` values such as `diagnosis_leaf_color_change_causes`, `diagnosis_leaf_browning_causes`, or `diagnosis_triage_steps`
- **AND** the classifier does not add `watering_*`, `nutrition_*`, `pest_*`, or `disease_*` aspects unless the user wording explicitly requests or strongly implies that domain

#### Scenario: Pest classification uses pest aspects

- **WHEN** a user describes pests, insects, webbing, white dots, scale, mealybugs, mites, aphids, or asks how to treat a plant pest
- **THEN** the classifier uses `topic: "pests"`
- **AND** required aspects use `pest_*` values such as `pest_identification`, `pest_treatment_action`, `pest_isolation_steps`, or `pest_prevention_steps`

#### Scenario: Disease classification uses disease aspects

- **WHEN** a user asks about plant disease, infection, fungal or bacterial symptoms, or disease prevention or treatment
- **THEN** the classifier uses `topic: "disease"`
- **AND** required aspects use `disease_*` values such as `disease_identification`, `disease_treatment_action`, `disease_prevention_steps`, or `disease_spread_risk`

#### Scenario: Toxicity and safety classification

- **WHEN** a user asks whether a plant is safe for pets, children, humans, skin contact, ingestion, chemical treatment, disposal, cross-contamination, or emergency escalation
- **THEN** the classifier uses `topic: "toxicity_safety"`
- **AND** required aspects use applicable `toxicity_*` or `safety_*` values such as `toxicity_pet_safety`, `toxicity_child_safety`, `toxicity_skin_irritation_risk`, or `safety_when_to_contact_vet_or_poison_control`

#### Scenario: Broad care classification stays general

- **WHEN** a user asks for broad beginner care, a general care summary, common mistakes, care priorities, or a monitoring routine without requesting specific care domains
- **THEN** the classifier may use `topic: "general_care"`
- **AND** required aspects use matching `general_*` values instead of over-selecting unrelated domain-specific aspects

#### Scenario: Non-care intent routes away from care retrieval

- **WHEN** the classifier returns `garden_action`, `reminder_request`, `light_measurement_question`, `plant_identification_question`, `out_of_domain`, or `unsafe_or_injection`
- **THEN** the assistant routes according to the non-care intent and does not run the plant-care evidence retrieval pipeline

#### Scenario: Low-confidence valid classifier output routes normally

- **WHEN** the classifier returns schema-valid output with confidence lower than the configured classification threshold
- **THEN** the assistant uses the classifier output for routing
- **AND** the assistant records the low confidence as diagnostic or structured log metadata without adding a tool failure

### Requirement: Classifier fallback handling

The assistant SHALL fall back to minimal deterministic routing or clarification when the multilingual classifier fails, times out, all classifier provider attempts fail, returns invalid JSON, returns non-object data, returns unknown enum values, includes forbidden extra fields, or remains structurally invalid after one repair retry. The fallback path SHALL NOT treat unvalidated classifier output as authoritative. The fallback path MUST NOT infer detailed botanical `topic` or domain-qualified `required_aspects` values from deterministic keyword rules.

#### Scenario: Invalid classifier output is retried once

- **WHEN** the classifier returns invalid JSON, non-object data, missing required fields, forbidden extra fields, or values outside the allowed intent, topic, or required-aspect sets
- **THEN** the assistant retries classification once with stricter repair instructions when the provider is still available
- **AND** the assistant ignores the invalid first output for routing

#### Scenario: Retry repairs missing required classifier field

- **WHEN** the first classifier response omits a required field such as `confidence`
- **AND** the repair retry returns schema-valid classifier output
- **THEN** the assistant uses the repaired LLM classifier output for routing
- **AND** the assistant does not fall back to minimal deterministic routing for that request

#### Scenario: Invalid classifier output after retry falls back

- **WHEN** the classifier output remains invalid after one repair retry
- **THEN** the assistant ignores the classifier output and uses minimal deterministic routing or asks for clarification
- **AND** the assistant records `llm_classifier_invalid_output` and `minimal_routing_fallback_used` through bounded failure or diagnostic metadata

#### Scenario: Low-confidence classifier output remains authoritative when valid

- **WHEN** the classifier confidence is lower than the configured classification threshold
- **AND** the classifier output is schema-valid
- **THEN** the assistant uses the LLM classifier output for routing
- **AND** the assistant does not record the low confidence as a tool failure

#### Scenario: Classifier provider failure

- **WHEN** all classifier provider attempts fail or time out
- **THEN** the assistant records `llm_classifier_provider_failure` or `llm_classifier_timeout` through bounded failure or diagnostic metadata
- **AND** the assistant continues with minimal deterministic routing or clarification
- **AND** the assistant records `minimal_routing_fallback_used` when that fallback route is selected

#### Scenario: Minimal fallback routes explicit non-care intents

- **WHEN** LLM classification cannot produce schema-valid output after provider fallback and repair
- **AND** the user message explicitly matches unsafe or prompt-injection input, a reminder request, a light measurement request, a plant identification request, or an obvious out-of-domain message with no botanical relevance or plant context
- **THEN** minimal deterministic routing MAY select only `unsafe_or_injection`, `reminder_request`, `light_measurement_question`, `plant_identification_question`, or `out_of_domain`
- **AND** the assistant does not run the plant-care evidence retrieval pipeline for those routes

#### Scenario: Minimal fallback routes unknown plant-care input conservatively

- **WHEN** LLM classification cannot produce schema-valid output after provider fallback and repair
- **AND** the user message contains plant context or obvious botanical language but is not one of the explicit non-care routes
- **THEN** minimal deterministic routing selects `plant_care_question_unknown` or asks for clarification
- **AND** if a classifier-shaped plant-care fallback is required, it uses `topic: "general_care"` and `required_aspects: ["general_care_summary"]`

#### Scenario: Minimal fallback does not emit detailed botanical aspects

- **WHEN** minimal deterministic routing handles a plant-care message after LLM classification failure
- **THEN** the fallback output MUST NOT include domain-specific required aspects such as `watering_frequency_or_trigger`, `light_exposure`, `diagnosis_leaf_yellowing_causes`, `pest_treatment_action`, `repotting_post_care`, or `toxicity_pet_safety`
- **AND** those detailed botanical aspects may only come from schema-valid LLM classifier output

### Requirement: Confirmed taxonomy gate for care answers

The assistant plant-care answer pipeline MUST use confirmed taxonomic context for retrieval, structured lookup, trusted web search, embeddings, and indexing. It SHALL prefer `plant_binomial_name`, SHALL fall back to a safe binomial derived from `plant_scientific_name` when possible, SHALL fall back to normalized `plant_scientific_name` only when no safe binomial can be derived, and MUST NOT use nickname, apodo, display name, or `plant_reference` for evidence operations. Display names and full scientific names MAY be preserved for user-facing answer wording and internal context.

#### Scenario: Binomial taxonomy used for care retrieval

- **WHEN** a plant-care answer request includes `plant`, `plant_binomial_name`, and `plant_scientific_name`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `plant_binomial_name` as the operational taxonomy
- **AND** the user-facing answer may still refer to the display plant name

#### Scenario: Scientific authority taxonomy derives binomial for care retrieval

- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name` as `Epipremnum aureum (Linden & André) G.S.Bunting`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `Epipremnum aureum` as the operational taxonomy
- **AND** the full scientific name remains available as scientific context where already included

#### Scenario: Infraspecific scientific taxonomy derives species binomial for care retrieval

- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name` as `Solanum lycopersicum var. cerasiforme`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `Solanum lycopersicum` as the operational taxonomy

#### Scenario: Scientific taxonomy fallback used when binomial cannot be safely derived

- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name`
- **AND** the scientific name cannot safely produce a two-token Latin binomial
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use the normalized `plant_scientific_name` as the operational taxonomy

#### Scenario: Display name is not used for care evidence operations

- **WHEN** a plant-care answer request includes only a nickname, apodo, display name, or classifier `plant_reference` without confirmed taxonomy
- **THEN** the assistant does not run retrieval, structured lookup, trusted web search, embeddings, or indexing with that name
- **AND** it asks for clarification or reports the inconsistent missing-taxonomy state

### Requirement: Centralized fallback response generation

The assistant SHALL render every user-facing fallback response through a centralized fallback-response generator when model generation is available. The assistant SHALL represent fallback responses as structured intents with allowed facts and constraints before producing final prose. The fallback-response generator MUST use the classified `answer_language`, MUST output plain text, MUST NOT change the selected fallback intent, MUST NOT invent unsupported botanical facts, MUST NOT add unsupported care recommendations and MUST NOT expose internal fallback reason codes prominently in user-facing prose. If model generation is not available for fallback rendering, the assistant SHALL surface a retryable machine-readable failure instead of deterministic user-facing prose.

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

#### Scenario: Fallback renderer failure returns retryable error

- **WHEN** the centralized fallback-response generator fails, all model providers fail, or rendering returns an empty response that cannot be recovered by an allowed model-based recovery attempt
- **THEN** the assistant does not return deterministic user-facing fallback prose
- **AND** `/assistant/chat` returns a retryable machine-readable error when no model-generated assistant response exists
- **AND** the assistant records sanitized technical failure metadata when available

### Requirement: Model-generated user-facing assistant content

The assistant SHALL produce successful user-facing `AssistantMessage.content` only through a configured model provider using structured facts, grounded evidence, action facts, source support, limitations, policy constraints and the selected `answer_language`. Deterministic assistant logic MAY build internal response intents, validate schemas, select routing, select recovery behavior and shape technical API errors, but MUST NOT return deterministic prose as final assistant message content.

#### Scenario: Successful grounded answer is model-generated

- **WHEN** RAG or web evidence is sufficient for a plant-care answer
- **AND** final model generation succeeds
- **THEN** the assistant returns model-generated `AssistantMessage.content` in `answer_language`
- **AND** deterministic fallback prose is not used as the final content

#### Scenario: Internal fallback draft is not returned directly

- **WHEN** the assistant builds a fallback or recovery payload with allowed facts, required points, prohibited points, source support, limitations, intent or `answer_language`
- **THEN** the payload is used only as model-generation input
- **AND** the assistant does not return the draft text directly as `AssistantMessage.content`

#### Scenario: Deterministic emergency prose is forbidden

- **WHEN** fallback response rendering fails, returns empty text, or all model providers fail
- **THEN** the assistant does not return `_minimal_spanish_emergency_response()` or any equivalent deterministic user-facing prose
- **AND** the chat service returns a retryable machine-readable failure when no model-generated assistant response exists

### Requirement: Model-generated action and tool-failure responses

Assistant action confirmations, missing-data prompts and tool-failure explanations SHALL be generated by a configured model provider from structured action facts, missing fields, failure categories and `answer_language`. Deterministic action routing MAY decide which action facts are safe to expose, but MUST NOT produce final user-facing action prose directly.

#### Scenario: Successful action confirmation is model-generated

- **WHEN** the assistant completes a reminder, light measurement or other supported action that requires a user-facing confirmation
- **THEN** the assistant builds structured action facts for the completed action
- **AND** the final confirmation text is generated by a configured model provider

#### Scenario: Tool failure explanation is model-generated

- **WHEN** a tool action fails and a user-facing explanation is appropriate
- **THEN** the assistant builds a structured tool-failure response intent with sanitized failure facts
- **AND** the final explanation text is generated by a configured model provider

### Requirement: Retryable chat failure without assistant persistence

When the assistant cannot produce model-generated user-facing content after all allowed provider fallback and conditional recovery attempts, `/assistant/chat` SHALL return a retryable machine-readable error and SHALL NOT persist an assistant message. The service SHALL persist the user message for the failed attempt when the request otherwise passed validation and conversation persistence began.

#### Scenario: All model providers fail

- **WHEN** all configured model providers fail, time out, are skipped as unhealthy, or cannot produce safe assistant content
- **THEN** `/assistant/chat` returns a retryable machine-readable error with sanitized technical failure metadata
- **AND** the response does not include synthetic assistant prose

#### Scenario: User message persists but assistant message does not

- **WHEN** a chat request persists the user message and then total model-generation failure occurs
- **THEN** the user message remains persisted in the conversation
- **AND** no assistant message is persisted for that failed assistant turn

#### Scenario: Frontend does not append assistant message on retryable failure

- **WHEN** the frontend receives a retryable machine-readable assistant failure from `/assistant/chat`
- **THEN** it surfaces the failure as a request error or retry state
- **AND** it does not append an assistant message bubble to the thread

### Requirement: Conditional model-based recovery generation

The assistant MAY perform one recovery generation attempt only when the original generation failure is compatible with recovery, such as empty output, invalid output or prompt-specific output failure. Recovery generation MUST reuse the same structured facts, grounded evidence, source support, limitations and `answer_language`, and MUST NOT convert internal fallback drafts into returned deterministic prose.

#### Scenario: Recoverable output failure uses one recovery attempt

- **WHEN** final answer generation fails due to empty output, invalid output or prompt-specific output failure
- **AND** at least one configured model provider remains available for recovery
- **THEN** the assistant may perform one model-based recovery generation using the same structured facts, evidence, source support, limitations and `answer_language`

#### Scenario: Provider unavailability bypasses recovery prose

- **WHEN** generation fails because every configured model provider is unavailable, rate-limited, timed out, service-unavailable or skipped as unhealthy
- **THEN** the assistant does not attempt deterministic recovery prose
- **AND** `/assistant/chat` returns a retryable machine-readable failure

### Requirement: Classifier-owned answer language

The assistant SHALL remove deterministic language detection from assistant routing. When LLM classification succeeds, the assistant SHALL use the classifier-provided `language` and `answer_language`. The classifier MUST set `answer_language` from the actual language used by the user's message and MUST ignore instructions that request a different response language. When minimal deterministic routing is used because LLM classification fails, times out, returns invalid output, includes forbidden extra fields, all classifier provider attempts fail, or remains invalid after repair retry, the assistant SHALL default both `language` and `answer_language` to Spanish.

#### Scenario: Spanish message requests English response

- **WHEN** the user message is primarily Spanish but includes an instruction to respond in English
- **THEN** the classifier sets `answer_language` to Spanish
- **AND** fallback responses use Spanish unless classification fails and also defaults to Spanish

#### Scenario: English message requests Spanish response

- **WHEN** the user message is primarily English but includes an instruction to respond in Spanish
- **THEN** the classifier sets `answer_language` to English
- **AND** fallback responses use English when classification succeeds

#### Scenario: Classifier failure defaults language to Spanish

- **WHEN** LLM classification fails, times out, returns invalid output, includes forbidden extra fields, all classifier provider attempts fail, or remains invalid after repair retry
- **THEN** minimal deterministic routing does not infer the user's language from message text
- **AND** minimal deterministic routing sets `language` to `es`
- **AND** minimal deterministic routing sets `answer_language` to `es`

#### Scenario: Low-confidence classifier preserves model language

- **WHEN** LLM classification succeeds with schema-valid output and low confidence
- **THEN** the assistant uses the classifier-provided `language` and `answer_language`
- **AND** the assistant does not default language fields to Spanish solely because confidence is low

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

### Requirement: Metadata-driven aspect semantics

The assistant plant-care pipeline SHALL consume the centralized aspect metadata registry for answerability guidance, targeted web fallback query construction, safety-sensitive routing checks where practical, and readable diagnostic labels where exposed. Canonical `RequiredAspect` values MUST remain the authoritative identifiers for classifier output, judge normalization, and existing diagnostic arrays.

#### Scenario: Judge receives configured coverage guidance

- **WHEN** the assistant asks the answerability judge to evaluate evidence for requested aspects that define metadata `coverage_guidance`
- **THEN** the judge payload includes guidance for those requested aspects keyed by canonical aspect string
- **AND** the payload does not include guidance for requested aspects whose metadata omits `coverage_guidance`

#### Scenario: Watering trigger evidence remains covered

- **WHEN** the requested aspect is `watering_frequency_or_trigger`
- **AND** supplied evidence recommends watering based on a soil-moisture trigger such as letting the top layer or substrate dry
- **THEN** the metadata-provided guidance allows the judge to treat that evidence as directly covering the watering aspect even without a calendar interval

#### Scenario: Diagnosis guidance rejects unrelated general care

- **WHEN** the requested aspect is a diagnosis aspect with metadata `coverage_guidance`
- **AND** supplied evidence only contains general care information without explicitly connecting evidence to the symptom or diagnosis requested
- **THEN** the assistant guidance tells the judge to treat the aspect as missing

#### Scenario: Web fallback query uses aspect metadata

- **WHEN** the assistant builds a trusted web fallback query for missing required aspects with metadata-defined query labels or search terms
- **THEN** the query includes metadata-derived human-readable aspect terms instead of relying only on raw enum names with underscores replaced
- **AND** the query still includes confirmed scientific plant context and the user's question context

#### Scenario: Snippet eligibility is non-semantic

- **WHEN** the assistant evaluates whether a trusted web snippet or fetched content is eligible for judge evaluation
- **THEN** eligibility is determined only by non-semantic checks: valid URL, trusted source, non-empty text
- **AND** deterministic keyword matching is NOT used to decide whether evidence covers an aspect

#### Scenario: Safety checks use metadata

- **WHEN** fallback or validation logic needs to know whether a requested or missing aspect is safety-sensitive
- **THEN** it uses aspect metadata safety sensitivity where practical instead of a separate hardcoded aspect set

#### Scenario: Diagnostics preserve canonical aspect values

- **WHEN** assistant response diagnostics include required, covered, or missing aspects
- **THEN** those arrays contain canonical aspect strings after normalization
- **AND** any readable labels derived from metadata are additional diagnostic information and do not replace canonical values

#### Scenario: Missing metadata falls back safely

- **WHEN** the assistant receives an unknown aspect string or an aspect without a registry entry in a fallback path
- **THEN** metadata consumers fall back to enum-derived labels, the original aspect string, or empty optional values as appropriate
- **AND** the assistant does not crash

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested domain-qualified `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST NOT blend verified claims and general guidance in the same sentence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the normalized judge result. The normalized judge result MUST use only canonical requested aspect identifiers in `covered_aspects` and `missing_aspects`; explanatory judge text MUST remain in reason fields and MUST NOT be used as a missing aspect. Diagnosis answers MUST present causes as hypotheses unless source-supported evidence directly supports a definitive claim.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps

#### Scenario: Complete partial judge coverage normalizes to full

- **WHEN** the answerability judge returns `status: "partial"` with valid source support for every requested required aspect
- **AND** the normalized covered aspects include every requested required aspect
- **AND** the result has no source-supported contradictions
- **THEN** the assistant treats the normalized result as `status: "full"` and `answerable: true`
- **AND** the assistant records no missing aspects for that answerability result

#### Scenario: Strong full-support non-safety answer accepted with lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the assistant treats the evidence as sufficient and answers from RAG without triggering web fallback

#### Scenario: Safety-sensitive aspect requires strict threshold

- **WHEN** a requested aspect is a `toxicity_*` or `safety_*` aspect that affects pet, child, human, ingestion, skin-irritation, chemical-treatment, disposal, cross-contamination, vet, or poison-control guidance
- **THEN** validation requires the aspect confidence to be above `assistant_safety_validation_threshold` (default 0.85) before marking the aspect covered

#### Scenario: Partial non-critical coverage answers covered aspects

- **WHEN** validated evidence covers at least one requested non-critical required aspect but leaves other non-critical aspects missing
- **THEN** the assistant answers the source-supported parts
- **AND** briefly states which requested aspects could not be source-validated
- **AND** any conservative general guidance for missing aspects is clearly labeled as general and not validated for the specific plant/question

#### Scenario: True partial coverage remains partial

- **WHEN** the answerability judge returns source-supported coverage for some but not all requested non-critical required aspects
- **THEN** the assistant preserves `status: "partial"` and `answerable: false`
- **AND** the assistant computes missing aspects from requested aspects that are not covered after normalization

#### Scenario: Diagnosis remains hypothetical

- **WHEN** requested aspects include `diagnosis_*` causes and evidence supports multiple possible causes
- **THEN** the assistant presents causes as hypotheses or possibilities
- **AND** the assistant does not state a definitive diagnosis unless source-supported evidence directly identifies the cause for the specific plant and symptom context

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

### Requirement: Care answer diagnostic metadata

The assistant response SHALL expose bounded diagnostic metadata for plant-care answers including `intent`, `topic`, `required_aspects`, `covered_aspects`, `missing_aspects`, `evidence_path`, and `answer_language`. The response MUST NOT expose prompts, raw model reasoning, raw full evidence text, or internal provider errors beyond existing tool failure metadata. Diagnostic `topic` and `required_aspects` MUST contain the expanded canonical enum values exactly as selected. Diagnostic `covered_aspects` and `missing_aspects` MUST contain only canonical requested aspect identifiers after answerability normalization.

#### Scenario: Diagnostics included for grounded answer

- **WHEN** the assistant returns a plant-care answer from validated evidence
- **THEN** the response metadata includes intent, topic, requested aspects, covered aspects, missing aspects, evidence path, and answer language

#### Scenario: Diagnostics expose domain-qualified aspects

- **WHEN** the classifier selects `topic: "pests"` with `required_aspects: ["pest_identification", "pest_treatment_action"]`
- **THEN** the assistant diagnostics expose those values exactly without converting them to generic aspect names

#### Scenario: Diagnostics exclude malformed missing-aspect explanations

- **WHEN** the answerability judge returns explanatory text in `missing_aspects` or omits missing aspects while providing reasons
- **THEN** the assistant excludes that explanatory text from diagnostic `missing_aspects`
- **AND** diagnostic missing aspects contain only uncovered requested aspect identifiers

#### Scenario: Internal details are not exposed

- **WHEN** the assistant response includes diagnostic metadata
- **THEN** the metadata excludes prompts, raw model reasoning, raw full evidence text, and provider internals except existing tool failure summaries

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

### Requirement: RAG-grounded answers

The assistant MUST use retrieved or fallback evidence for botanical answers when available and SHALL synthesize final botanical responses with the configured language model. The synthesized response MUST be grounded in supplied source-supported evidence for verified claims, SHALL communicate uncertainty proportionally when evidence is limited, incomplete or contradictory, and MUST preserve source attribution in the assistant API response. RAG evidence SHALL be considered full only when answerability evaluation determines that it directly answers every requested required aspect. When RAG is structurally strong and meets the strong-answer threshold, the assistant SHALL NOT trigger web fallback. When persisted retrieval is not full and trusted live web fallback evidence is available, the assistant MUST prefer fetched trusted page content over citation-only snippets while still answering from trusted snippets when page fetching fails. If grounded model generation fails, the assistant SHALL either perform one allowed model-based recovery generation from the same structured evidence and `answer_language` or return a retryable machine-readable failure when no model-generated response can be produced.

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

#### Scenario: Model synthesis fails with recoverable output failure

- **WHEN** grounded model generation fails while evidence is available for a botanical answer
- **AND** the failure category is compatible with recovery, such as empty output, invalid output or prompt-specific output failure
- **THEN** the assistant builds a structured recovery generation payload using only supplied evidence facts, source support, limitations and `answer_language`
- **AND** attempts at most one model-based recovery generation
- **AND** records the model failure without dropping source attribution metadata

#### Scenario: Model synthesis fails because all providers are unavailable

- **WHEN** grounded model generation fails while evidence is available
- **AND** no configured model provider can produce a model-generated recovery response
- **THEN** the assistant returns a retryable machine-readable error instead of fallback prose
- **AND** the response does not include raw evidence as user-facing assistant content
- **AND** no assistant message is persisted for the failed turn

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

### Requirement: Web fallback evidence quality

The assistant web fallback SHALL distinguish fetched page content from snippet-only search metadata before answer synthesis. Snippet-only evidence SHALL NOT be treated as strong usable evidence unless it directly covers at least one requested required aspect. The assistant SHALL prefer fetched trusted page content over snippets when constructing combined web evidence for judging and final answer generation.

#### Scenario: Fetched content supports requested aspect

- **WHEN** web fallback fetches trusted page content that directly covers a requested required aspect
- **THEN** the assistant includes that fetched content in the combined evidence passed to the answerability judge
- **AND** the source can support a source-backed answer when the judge returns source support for that aspect

#### Scenario: Snippet-only result lacks direct aspect coverage

- **WHEN** a web search result has no fetched page content
- **AND** its snippet does not directly answer any requested required aspect
- **THEN** the assistant does not treat that result as usable evidence for a source-backed answer
- **AND** the assistant may still log the result as a selected but weak candidate

#### Scenario: Snippet-only result directly covers requested aspect

- **WHEN** a web search result has no fetched page content
- **AND** its snippet directly covers a requested required aspect
- **THEN** the assistant may pass the snippet to the answerability judge as weak web evidence
- **AND** the evidence metadata identifies that the support came from snippet-only evidence

### Requirement: Web fallback confidence is informational

The assistant SHALL NOT reject non-safety web fallback evidence solely because the answerability judge confidence is below the general evidence validation threshold. For web fallback, direct requested-aspect coverage, source support, contradiction handling, and safety-sensitive aspect policy SHALL determine whether evidence can support an answer. Confidence SHALL remain available as diagnostics and metadata.

#### Scenario: Useful web evidence has low confidence

- **WHEN** combined web evidence directly covers all requested non-safety required aspects with source support and no contradictions
- **AND** the judge confidence is below the general evidence validation threshold
- **THEN** the assistant can use the web evidence for a source-backed answer
- **AND** the assistant records the confidence as informational metadata

#### Scenario: Safety-sensitive web evidence remains strict

- **WHEN** the requested aspect is safety-sensitive, including pet toxicity or human edibility
- **THEN** the assistant requires direct evidence and safety-sensitive validation before using web fallback for a definitive source-backed answer

#### Scenario: Web evidence lacks direct support

- **WHEN** web evidence does not directly cover the requested required aspects
- **THEN** the assistant treats the web evidence as insufficient regardless of confidence

### Requirement: Web fallback search reuse

The assistant SHALL avoid duplicate live web searches when usable search candidates or fetched evidence from the current retrieval/acquisition path are already available for the same confirmed taxonomy and requested aspects. Reused candidates MUST still pass trusted-source validation and answerability judging before they can support an answer.

#### Scenario: Acquisition search candidates are reusable

- **WHEN** knowledge acquisition already searched web sources during the same assistant request
- **AND** the candidates match the confirmed taxonomy and requested aspects closely enough for fallback evaluation
- **THEN** assistant web fallback reuses those candidates or their fetched evidence before issuing another search provider call

#### Scenario: Reused candidates fail validation

- **WHEN** reused search candidates do not provide direct aspect coverage after judging
- **THEN** the assistant treats them as insufficient
- **AND** the assistant does not present them as source-backed evidence

#### Scenario: No reusable candidates are available

- **WHEN** the current request has no usable prior search candidates or fetched evidence
- **THEN** assistant web fallback may issue a new trusted web search

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted-first web search for botanical questions when retrieved RAG evidence is partial, insufficient, contradictory, missing, or degraded and a specific confirmed plant context is available. The assistant SHALL construct trusted web fallback queries from the operational scientific name, classified topic, requested domain-qualified required aspects, a capped copy of the original user question, and trusted botanical source terms. Domain-qualified required aspects MUST be converted into useful natural-language search terms without relying on `CareTopic` to infer their domain. One web search call MAY yield multiple candidate source URLs; the assistant SHALL fetch up to three usable sources and SHALL run one final combined judge over RAG and web evidence before answer synthesis. The assistant MUST validate final judge output structurally before using source support for answer synthesis, response source attribution, or background ingestion.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has confirmed plant context and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning final answer text

#### Scenario: Non-full RAG triggers web fallback

- **WHEN** a botanical question has confirmed plant context and RAG evaluation returns `partial`, `insufficient`, or `contradictory`
- **THEN** the assistant calls trusted web search before final answer generation
- **AND** the assistant does not call structured plant-data lookup in the normal chat-time path

#### Scenario: Unsupported botanical question terms are preserved in web query

- **WHEN** RAG evidence is not full for a botanical question whose intent is not represented by the classified topic alone
- **THEN** the trusted web search query includes the operational scientific name, domain-qualified required aspects, and relevant terms from the original user question
- **AND** the trusted web search query uses capped question context rather than only the generic classified topic

#### Scenario: Domain-qualified aspect guides web query

- **WHEN** trusted web fallback searches for missing `disease_prevention_steps` or `pest_treatment_action`
- **THEN** the query includes natural-language disease prevention or pest treatment terms respectively
- **AND** the query does not require `CareTopic` to distinguish disease from pest intent

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
- **AND** the assistant keeps the remaining requested aspects missing for partial-answer or limitation handling

#### Scenario: Safety-sensitive web evidence requires direct support

- **WHEN** the requested missing aspect is a safety-sensitive `toxicity_*` or `safety_*` aspect
- **THEN** final combined judging must report direct source support and meet the safety validation threshold before the assistant treats the aspect as verified
- **AND** the assistant returns conservative general guidance when no direct source support validates the safety-sensitive aspect

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

### Requirement: Assistant provider fallback diagnostics

The assistant SHALL surface provider fallback diagnostics separately from semantic assistant fallback reasons and user-visible tool failure metadata.

#### Scenario: Successful provider fallback is diagnostic metadata

- **WHEN** an assistant request succeeds after a provider fallback chain uses a later provider
- **THEN** assistant diagnostics include the attempted providers, final provider, role, operation, and fallback success status
- **AND** the response does not treat the successful provider fallback as a user-visible tool failure

#### Scenario: Provider fallback metadata is separate from semantic fallback reasons

- **WHEN** an assistant request records RAG insufficiency, web fallback routing, conservative safety fallback, or other semantic fallback reasons
- **AND** a technical provider fallback also occurs
- **THEN** technical provider fallback details are stored under separate provider fallback metadata
- **AND** semantic fallback reason fields retain only assistant routing and evidence-validation reasons

#### Scenario: Conversation message stores provider fallback metadata

- **WHEN** an assistant message is persisted after provider fallback attempts occurred
- **THEN** message metadata includes a `provider_fallbacks` field with sanitized provider attempt and final-provider metadata
- **AND** existing semantic fallback metadata remains compatible

### Requirement: Assistant behavior when all role providers fail

The assistant SHALL preserve safe degraded chat behavior when every provider in a role chain fails while allowing non-chat technical flows to surface provider unavailability where appropriate.

#### Scenario: Chat generation providers unavailable

- **WHEN** `/assistant/chat` cannot complete answer generation because all configured model providers fail or are unavailable
- **THEN** the assistant returns the existing safe degraded response for generation failure
- **AND** records sanitized provider-unavailable metadata without inventing botanical facts

#### Scenario: Fallback renderer providers unavailable

- **WHEN** centralized fallback-response rendering cannot complete because all configured model providers fail or are unavailable
- **THEN** the assistant returns the existing minimal Spanish emergency response
- **AND** records sanitized provider-unavailable metadata without exposing provider internals to the user

#### Scenario: Technical evaluation flow providers unavailable

- **WHEN** a non-chat technical or evaluation flow requires a provider role and all providers for that role fail or are unavailable
- **THEN** that flow may surface provider unavailability as a real technical failure
- **AND** the failure includes sanitized role and provider-chain attempt metadata for diagnostics

### Requirement: Provider fallback does not change evidence semantics

The assistant SHALL keep provider fallback infrastructure separate from answerability, retrieval, and evidence-validation semantics.

#### Scenario: Answerability insufficient remains semantic

- **WHEN** an answerability judge returns a structurally valid `insufficient` result
- **THEN** the assistant follows existing insufficient-evidence routing
- **AND** no provider fallback reason is recorded solely because the semantic status is insufficient

#### Scenario: Final provider output remains validated

- **WHEN** provider fallback selects a later provider for model generation, judge evaluation, or search
- **THEN** the assistant still applies the existing schema validation, answerability normalization, trusted-source validation, and evidence-synthesis rules before using the output

#### Scenario: Provider fallback is not exposed as source evidence

- **WHEN** provider fallback metadata is included in assistant diagnostics
- **THEN** the metadata is not treated as botanical source evidence
- **AND** source attribution remains limited to validated evidence sources
