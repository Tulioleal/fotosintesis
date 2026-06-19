## MODIFIED Requirements

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
