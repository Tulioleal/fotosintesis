## MODIFIED Requirements

### Requirement: Multilingual care intent classification

The assistant plant-care answer pipeline SHALL classify user input before retrieval using a closed multilingual classifier contract that includes `language`, `answer_language`, `intent`, `topic`, `required_aspects`, `plant_reference`, `confidence`, and `needs_retrieval`. The classifier SHALL use the configured cheaper/faster model from the same provider family as the main answer model. Classifier output MUST pass schema validation before it can drive routing or retrieval. Classifier confidence SHALL be retained as observability metadata and SHALL NOT be the sole reason to reject an otherwise valid classifier output. `topic` MUST be one of the expanded plant-care domains: `watering`, `light`, `soil_substrate`, `pot_container`, `nutrition`, `diagnosis`, `pests`, `disease`, `repotting`, `pruning`, `propagation`, `climate`, `humidity`, `growth_development`, `flowering_fruiting`, `seasonality_dormancy`, `toxicity_safety`, `taxonomy`, `ecology`, `general_care`, or `unknown`. Every `required_aspects` value MUST be domain-qualified and self-descriptive, except explicitly general values under the `general_*` domain. The classifier MUST NOT rely on `topic` to disambiguate a generic required aspect.

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

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested domain-qualified `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST NOT blend verified claims and general guidance in the same sentence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the normalized judge result. The normalized judge result MUST use only canonical requested aspect identifiers in `covered_aspects` and `missing_aspects`; explanatory judge text MUST remain in reason fields and MUST NOT be used as a missing aspect. Diagnosis answers MUST present causes as hypotheses unless source-supported evidence directly supports a definitive claim.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested domain-qualified required aspect above the configured threshold
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

#### Scenario: Diagnosis remains hypothetical

- **WHEN** requested aspects include `diagnosis_*` causes and evidence supports multiple possible causes
- **THEN** the assistant presents causes as hypotheses or possibilities
- **AND** the assistant does not state a definitive diagnosis unless source-supported evidence directly identifies the cause for the specific plant and symptom context

#### Scenario: True partial coverage remains partial

- **WHEN** the answerability judge returns source-supported coverage for some but not all requested non-critical required aspects
- **THEN** the assistant preserves `status: "partial"` and `answerable: false`
- **AND** the assistant computes missing aspects from requested aspects that are not covered after normalization

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
