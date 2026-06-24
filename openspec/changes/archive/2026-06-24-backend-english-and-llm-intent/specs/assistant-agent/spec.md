## MODIFIED Requirements

### Requirement: Multilingual care intent classification

The assistant plant-care answer pipeline SHALL classify user input before retrieval using a closed multilingual classifier contract that includes `language`, `answer_language`, `intent`, `topic`, `required_aspects`, `plant_reference`, `confidence`, and `needs_retrieval`. The classifier SHALL use the configured cheaper/faster model from the same provider family as the main answer model. Classifier output MUST pass schema validation before it can drive routing or retrieval. Classifier confidence SHALL be retained as observability metadata and SHALL NOT be the sole reason to reject an otherwise valid classifier output. Deterministic Spanish-keyword-based semantic intent detection SHALL NOT be used; the multilingual LLM classifier and explicit request fields (`plant`, `plant_binomial_name`, `plant_scientific_name`, reminder action fields, light measurement fields) are the sole semantic-intent path. Non-semantic safety boundaries (such as the prompt-injection `INJECTION_PATTERNS` check) MAY remain deterministic.

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

#### Scenario: Spanish-keyword deterministic routing is removed

- **WHEN** the LLM classifier is unavailable or returns invalid output and a non-English user message contains common Spanish reminder, light-measurement, edibility, pet-safety, native-range, or identification keywords
- **THEN** the assistant MUST NOT route the message to `reminder_request`, `light_measurement_question`, `plant_identification_question`, or a domain-specific care route based on those keywords
- **AND** the assistant falls back to `plant_care_question_unknown` (with `topic: "general_care"` and `required_aspects: ["general_care_summary"]`) or asks for clarification

### Requirement: Classifier fallback handling

The assistant SHALL fall back to minimal deterministic routing or clarification when the multilingual classifier fails, times out, all classifier provider attempts fail, returns invalid JSON, returns non-object data, returns unknown enum values, includes forbidden extra fields, or remains structurally invalid after one repair retry. The fallback path SHALL NOT treat unvalidated classifier output as authoritative. The fallback path MUST NOT infer detailed botanical `topic` or domain-qualified `required_aspects` values from deterministic keyword rules. The fallback path MUST NOT perform Spanish-keyword-based semantic intent detection for any intent other than `unsafe_or_injection`; reminder, light-measurement, plant-identification, edibility, pet-safety, native-range, and taxonomy routing are the exclusive responsibility of the LLM classifier and the explicit request fields. When classifier validation identifies missing required fields, the repair retry SHALL receive those missing field names explicitly and SHALL preserve any valid fields from the previous classifier response.

#### Scenario: Invalid classifier output is retried once

- **WHEN** the classifier returns invalid JSON, non-object data, missing required fields, forbidden extra fields, or values outside the allowed intent, topic, or required-aspect sets
- **THEN** the assistant retries classification once with stricter repair instructions when the provider is still available
- **AND** the assistant ignores the invalid first output for routing

#### Scenario: Retry repairs missing required classifier field

- **WHEN** the first classifier response omits a required field such as `intent` or `confidence`
- **AND** the repair retry receives explicit missing-field context and returns schema-valid classifier output
- **THEN** the assistant uses the repaired LLM classifier output for routing
- **AND** the assistant does not fall back to minimal deterministic routing for that request

#### Scenario: Invalid classifier output after retry falls back

- **WHEN** the classifier output remains invalid after one repair retry
- **THEN** the assistant ignores the classifier output and uses minimal deterministic routing or asks for clarification
- **AND** the assistant records `llm_classifier_invalid_output`, `classifier_invalid_output`, any extractable missing required field names, and `minimal_routing_fallback_used` through bounded failure or diagnostic metadata

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
- **AND** the user message explicitly matches unsafe or prompt-injection input or an obvious out-of-domain message with no botanical relevance or plant context
- **THEN** minimal deterministic routing MAY select only `unsafe_or_injection` or `out_of_domain`
- **AND** the assistant does not run the plant-care evidence retrieval pipeline for those routes
- **AND** the assistant MUST NOT select `reminder_request`, `light_measurement_question`, or `plant_identification_question` based on Spanish-keyword pattern matching in this fallback path

#### Scenario: Minimal fallback routes unknown plant-care input conservatively

- **WHEN** LLM classification cannot produce schema-valid output after provider fallback and repair
- **AND** the user message contains plant context or obvious botanical language but is not one of the explicit non-care routes
- **THEN** minimal deterministic routing selects `plant_care_question_unknown` or asks for clarification
- **AND** if a classifier-shaped plant-care fallback is required, it uses `topic: "general_care"` and `required_aspects: ["general_care_summary"]`

#### Scenario: Minimal fallback does not emit detailed botanical aspects

- **WHEN** minimal deterministic routing handles a plant-care message after LLM classification failure
- **THEN** the fallback output MUST NOT include domain-specific required aspects such as `watering_frequency_or_trigger`, `light_exposure`, `diagnosis_leaf_yellowing_causes`, `pest_treatment_action`, `repotting_post_care`, or `toxicity_pet_safety`
- **AND** those detailed botanical aspects may only come from schema-valid LLM classifier output

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested domain-qualified `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST integrate source-backed claims and any complementary general guidance in a continuous narrative that signals the origin of each part through soft linguistic connectors (for example, `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`). Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the normalized judge result. The normalized judge result MUST use only canonical requested aspect identifiers in `covered_aspects` and `missing_aspects`; explanatory judge text MUST remain in reason fields and MUST NOT be used as a missing aspect. Diagnosis answers MUST present causes as hypotheses unless source-supported evidence directly supports a definitive claim. Final prose MUST NOT include URLs, institution names, or blocks labeled `Source-backed`, `Sources`, `References`, or equivalents; source attribution is delivered through the structured `sources[]` response field, not through the prose. The `_grounded_answer_prompt` MUST be written in English, MUST NOT instruct the model to add an attribution block, source link, or institutional name based on `evidence_type` (including `evidence_type == "structured_api"`), MUST instruct the model to integrate source-backed claims and any complementary general guidance into continuous narrative prose using soft linguistic connectors (for example, `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`), and MUST include a display-name preservation paragraph that instructs the model to address the plant by the selected plant name (the display name / nickname) and never replace it with the common name, scientific name, or binomial from the evidence, taxonomy context, or source metadata. The connector-priority paragraph MUST instruct the model that soft linguistic connectors (for example, `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`) are preferred over direct repetition of the same connective phrase in adjacent paragraphs, to avoid stilted prose.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks
- **AND** source metadata is delivered only through the structured `sources[]` field

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
- **THEN** the assistant answers the source-supported parts in continuous prose
- **AND** briefly states which requested aspects could not be source-validated
- **AND** any conservative general guidance for missing aspects is introduced with a soft linguistic connector (for example, `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`) and is treated as general and not source-validated for the specific plant/question
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

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
- **AND** any conservative general guidance is introduced with a soft linguistic connector and is treated as general and not source-validated for the specific plant/question
- **AND** the assistant does not cite general guidance as source-backed evidence
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Safety-sensitive missing evidence returns conservative guidance

- **WHEN** a safety-sensitive care question lacks direct validated evidence for the primary safety aspect at the configured safety-sensitive threshold
- **THEN** the assistant states that direct source-backed evidence was unavailable for the specific plant/question
- **AND** the assistant may provide conservative safety guidance introduced with a soft linguistic connector and treated as general and not source-validated
- **AND** the assistant does not claim the plant is safe, toxic, edible, or consumable without direct evidence
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks

#### Scenario: Contradictory evidence is presented without definitive claim

- **WHEN** final evidence validation reports contradictory source-supported claims for a requested aspect
- **THEN** the assistant states in generic terms that the consulted sources conflict (for example, "there is contradictory information among the consulted sources about X") without naming or linking specific sources
- **AND** the response prose contains no URLs, institution names, or `Source-backed` / `Sources` / `References` blocks
- **AND** the assistant avoids a definitive recommendation from the contradictory evidence
- **AND** source metadata continues to be delivered only through the structured `sources[]` field

### Requirement: Disclaimed general guidance answer mode

The assistant SHALL support a runtime-only `general_guidance_with_disclaimer` answer mode for plant-care questions when validated evidence is relevant but incomplete or insufficient and the missing guidance is not safety-sensitive. This mode MUST preserve the classified `answer_language`, MUST clearly separate source-validated facts from general model guidance, MUST explicitly state which requested information was not validated by retrieved sources, MUST NOT cite general guidance as evidence, and MUST request additional details when they would materially improve the answer. The disclaimed-guidance prompt (`_general_guidance_with_disclaimer_prompt`) MUST be written in English and MUST include a display-name preservation paragraph that instructs the model to address the plant by the selected plant name (the display name / nickname) and never replace it with the common name, scientific name, or binomial from the evidence, taxonomy context, or source metadata.

#### Scenario: Full evidence keeps grounded answer behavior

- **WHEN** answerability validation returns full coverage for all requested required aspects with valid source support and no contradictions
- **THEN** the assistant uses the existing grounded answer behavior
- **AND** the assistant does not label the answer as runtime-only general guidance

#### Scenario: Partial non-safety evidence includes limitations and optional guidance

- **WHEN** answerability validation returns source-supported coverage for at least one requested non-safety aspect but leaves other non-safety aspects missing
- **THEN** the assistant answers the validated source-supported parts with any applicable citations
- **AND** the assistant states which requested aspects were not validated by the available sources
- **AND** any guidance for missing aspects is clearly labeled as general guidance that was not validated by the retrieved sources

#### Scenario: Insufficient non-safety evidence with relevant context provides disclaimed guidance

- **WHEN** answerability validation returns `status: "insufficient"` for a plant-care question
- **AND** the assistant has relevant retrieved evidence, web evidence, validated plant context, or confirmed taxonomy for the request
- **AND** no missing requested aspect is safety-sensitive
- **THEN** the assistant may generate a `general_guidance_with_disclaimer` answer instead of a generic insufficient-evidence fallback
- **AND** the answer states that the retrieved sources did not validate the requested answer
- **AND** the answer presents any general guidance in a clearly labeled non-validated section
- **AND** the answer asks for a close photo, symptoms, location, treatment history, or other missing details when useful

#### Scenario: Pest question receives cautious non-validated guidance

- **WHEN** a user asks about small white insects under leaves
- **AND** retrieved evidence or combined evidence does not validate the exact pest identity or a treatment for the specific plant
- **AND** the requested aspects are limited to non-safety pest identification, inspection, isolation, or non-destructive care actions
- **THEN** the assistant states that the sources did not confirm the insect identity or validate a specific treatment
- **AND** the assistant may provide general, non-validated guidance such as isolating the plant, inspecting leaf undersides, removing visible insects with water or a damp cloth, and requesting a close photo
- **AND** the assistant does not recommend insecticides unless the claim is directly source-supported and includes appropriate label or expert-use constraints

#### Scenario: No relevant plant context keeps clarification behavior

- **WHEN** answerability validation returns insufficient evidence
- **AND** the assistant has no relevant plant context, no confirmed taxonomy, no relevant retrieved evidence, and no useful source-supported facts
- **THEN** the assistant uses the existing clarification or insufficient-evidence fallback behavior
- **AND** the assistant does not invent plant-specific guidance

#### Scenario: Safety-sensitive missing aspects remain conservative

- **WHEN** a requested aspect involves toxicity, edibility, pets, children, medical-like exposure, chemical dosing, severe disease diagnosis, pesticide instructions, or another safety-sensitive care boundary
- **AND** direct source-supported evidence does not validate the specific safety claim at the configured safety threshold
- **THEN** the assistant does not use general model knowledge to claim safety, toxicity, edibility, exposure outcomes, dosing, diagnosis certainty, or pesticide instructions
- **AND** the assistant uses the existing conservative safety fallback or answers only directly source-supported safety facts

### Requirement: Safety and failure handling

The assistant MUST resist prompt injection and MUST NOT claim a failed tool action was completed. The prompt-injection defense MUST be expressed in English-language `INJECTION_PATTERNS` entries; deterministic Spanish-keyword pattern matching SHALL NOT be used for injection resistance. The conservative safety fallback template (`_conservative_safety_answer`) MUST be written in English.

#### Scenario: Tool fails

- **WHEN** a tool call fails during a requested action
- **THEN** the assistant states that the action was not completed and logs the failure

#### Scenario: English prompt-injection pattern matches an English attack

- **WHEN** a user message contains an English-language prompt-injection attempt such as `ignore the instructions` or `omit the rules`
- **THEN** the English `INJECTION_PATTERNS` entry matches the message
- **AND** the assistant routes the message as `unsafe_or_injection`

#### Scenario: Spanish prompt-injection pattern entry is removed

- **WHEN** a Spanish-language prompt-injection attempt arrives and the LLM classifier is available
- **THEN** the assistant relies on the LLM classifier to detect the injection rather than on a deterministic Spanish-keyword pattern entry
- **AND** the assistant still routes the message as `unsafe_or_injection` when the classifier identifies the injection

## REMOVED Requirements

### Requirement: Deterministic Spanish-keyword semantic intent detection
**Reason**: The Spanish-keyword based deterministic intent detection inside `_deterministic_classification` (and the helper functions `_is_light_measurement_request`, `_message_has_plant_context`, `_is_edibility_question`, `_is_pet_safety_question`, `_extract_recurrence`, `_extract_reminder_action`, `_wants_reminder_suggestion`) routes semantic intents based on translated word lists, regexes, and English/Spanish-only heuristics. This is explicitly forbidden by `openspec/config.yaml`. The multilingual LLM classifier and the explicit request fields are the sole semantic-intent path.

**Migration**: All semantic intent detection is now performed by the multilingual LLM classifier. The LLM classifier's `intent`, `topic`, and `required_aspects` outputs drive routing. Reminder and light-measurement flows continue to use the explicit `reminder_action` / `light_measurement` request fields and the user-confirmation flow. The deterministic fallback retains only the non-semantic `unsafe_or_injection` branch and an empty/passthrough for `plant_care_question_unknown` / `general_care`.
