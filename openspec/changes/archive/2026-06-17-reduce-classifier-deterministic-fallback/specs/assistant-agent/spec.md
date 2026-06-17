## MODIFIED Requirements

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
- **THEN** the classifier output includes all applicable canonical required aspects for the requested watering and light information

#### Scenario: Non-care intent routes away from care retrieval

- **WHEN** the classifier returns `garden_action`, `reminder_request`, `light_measurement_question`, `plant_identification_question`, `out_of_domain`, or `unsafe_or_injection`
- **THEN** the assistant routes according to the non-care intent and does not run the plant-care evidence retrieval pipeline

#### Scenario: Low-confidence valid classifier output routes normally

- **WHEN** the classifier returns schema-valid output with confidence lower than the configured classification threshold
- **THEN** the assistant uses the classifier output for routing
- **AND** the assistant records the low confidence as diagnostic or structured log metadata without adding a tool failure

### Requirement: Classifier fallback handling

The assistant SHALL fall back to deterministic classification or clarification when the multilingual classifier fails, times out, returns invalid JSON, returns non-object data, returns unknown enum values, includes forbidden extra fields, or remains structurally invalid after one repair retry. The fallback path SHALL NOT treat unvalidated classifier output as authoritative.

#### Scenario: Invalid classifier output is retried once

- **WHEN** the classifier returns invalid JSON, non-object data, missing required fields, forbidden extra fields, or values outside the allowed intent, topic, or required-aspect sets
- **THEN** the assistant retries classification once with stricter repair instructions when the provider is still available
- **AND** the assistant ignores the invalid first output for routing

#### Scenario: Retry repairs missing required classifier field

- **WHEN** the first classifier response omits a required field such as `confidence`
- **AND** the repair retry returns schema-valid classifier output
- **THEN** the assistant uses the repaired LLM classifier output for routing
- **AND** the assistant does not fall back to deterministic classification for that request

#### Scenario: Invalid classifier output after retry falls back

- **WHEN** the classifier output remains invalid after one repair retry
- **THEN** the assistant ignores the classifier output and uses deterministic routing or asks for clarification
- **AND** the assistant records the classifier validation failure through existing failure metadata

#### Scenario: Low-confidence classifier output remains authoritative when valid

- **WHEN** the classifier confidence is lower than the configured classification threshold
- **AND** the classifier output is schema-valid
- **THEN** the assistant uses the LLM classifier output for routing
- **AND** the assistant does not record the low confidence as a tool failure

#### Scenario: Classifier provider failure

- **WHEN** the classifier provider fails or times out
- **THEN** the assistant records the failure through existing failure metadata and continues with deterministic routing or clarification

### Requirement: Classifier-owned answer language

The assistant SHALL remove deterministic language detection from assistant routing. When LLM classification succeeds, the assistant SHALL use the classifier-provided `language` and `answer_language`. The classifier MUST set `answer_language` from the actual language used by the user's message and MUST ignore instructions that request a different response language. When deterministic classification is used because LLM classification fails, times out, returns invalid output, includes forbidden extra fields, or remains invalid after repair retry, the assistant SHALL default both `language` and `answer_language` to Spanish.

#### Scenario: Spanish message requests English response

- **WHEN** the user message is primarily Spanish but includes an instruction to respond in English
- **THEN** the classifier sets `answer_language` to Spanish
- **AND** fallback responses use Spanish unless classification fails and also defaults to Spanish

#### Scenario: English message requests Spanish response

- **WHEN** the user message is primarily English but includes an instruction to respond in Spanish
- **THEN** the classifier sets `answer_language` to English
- **AND** fallback responses use English when classification succeeds

#### Scenario: Classifier failure defaults language to Spanish

- **WHEN** LLM classification fails, times out, returns invalid output, includes forbidden extra fields, or remains invalid after repair retry
- **THEN** deterministic routing still classifies intent, topic and required care aspects when possible
- **AND** deterministic routing sets `language` to `es`
- **AND** deterministic routing sets `answer_language` to `es`

#### Scenario: Low-confidence classifier preserves model language

- **WHEN** LLM classification succeeds with schema-valid output and low confidence
- **THEN** the assistant uses the classifier-provided `language` and `answer_language`
- **AND** the assistant does not default language fields to Spanish solely because confidence is low
