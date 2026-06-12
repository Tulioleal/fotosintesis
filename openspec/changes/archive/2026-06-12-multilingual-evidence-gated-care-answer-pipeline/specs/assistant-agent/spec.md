## ADDED Requirements

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
