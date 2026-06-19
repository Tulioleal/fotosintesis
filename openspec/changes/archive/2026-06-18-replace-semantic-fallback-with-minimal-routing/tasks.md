## 1. Classifier Fallback Implementation

- [x] 1.1 Locate the current deterministic classifier fallback in the assistant backend, including any keyword maps that infer botanical topics or required aspects.
- [x] 1.2 Replace the semantic fallback with a minimal routing fallback that only emits `unsafe_or_injection`, `reminder_request`, `light_measurement_question`, `plant_identification_question`, `out_of_domain`, or `plant_care_question_unknown`.
- [x] 1.3 Remove or stop using deterministic keyword logic that emits detailed botanical topics or domain-qualified required aspects such as watering, light, diagnosis, pest, repotting, or toxicity aspects.
- [x] 1.4 Preserve the existing LLM classifier success path, provider fallback, schema validation, and one repair retry before minimal deterministic routing is used.
- [x] 1.5 Ensure unknown plant-care fallback either asks a concise clarification or uses only `topic: "general_care"` with `required_aspects: ["general_care_summary"]` where downstream code requires classifier-shaped data.

## 2. Routing And Diagnostics

- [x] 2.1 Update assistant routing so explicit fallback routes continue to bypass plant-care evidence retrieval when appropriate.
- [x] 2.2 Update fallback metadata and logs to distinguish `llm_classifier_timeout`, `llm_classifier_invalid_output`, `llm_classifier_provider_failure`, and `minimal_routing_fallback_used`.
- [x] 2.3 Expose bounded diagnostics that identify minimal fallback provenance without presenting internal reason codes prominently in user-facing prose.
- [x] 2.4 Preserve deterministic fallback language defaults of `language: "es"` and `answer_language: "es"` without adding deterministic language detection.

## 3. Tests

- [x] 3.1 Update existing assistant classifier fallback tests that currently expect deterministic semantic topic or required-aspect inference.
- [x] 3.2 Add tests proving successful schema-valid LLM classifier output still preserves detailed `topic` and `required_aspects` values.
- [x] 3.3 Add tests for classifier invalid-output, timeout, and provider-failure paths proving minimal fallback is used only after provider fallback and repair are exhausted.
- [x] 3.4 Add tests proving minimal fallback still routes unsafe or injection input, reminder requests, light measurement requests, plant identification requests, obvious out-of-domain messages, and unknown plant-care messages.
- [x] 3.5 Add tests proving no deterministic fallback path emits domain-specific required aspects such as `watering_frequency_or_trigger`, `light_exposure`, `diagnosis_leaf_yellowing_causes`, `pest_treatment_action`, `repotting_post_care`, or `toxicity_pet_safety`.

## 4. Verification

- [x] 4.1 Run the focused backend assistant test suite covering classifier fallback and routing.
- [x] 4.2 Run any broader backend tests needed for provider fallback diagnostics if shared metadata code changes.
- [x] 4.3 Run OpenSpec validation or status checks for `replace-semantic-fallback-with-minimal-routing` before marking the change ready to apply.
