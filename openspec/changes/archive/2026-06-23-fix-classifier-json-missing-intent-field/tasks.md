## 1. Classifier Repair Path

- [x] 1.1 Update `_care_classifier_prompt` to enumerate every required classifier field and include a complete valid JSON example.
- [x] 1.2 Add helper logic in `backend/app/assistant/graph.py` to extract missing required field names from classifier validation errors without adding semantic keyword rules.
- [x] 1.3 Update `_care_classifier_repair_prompt` to receive missing field names, include a complete JSON template, and instruct the model to preserve valid fields from the previous response.
- [x] 1.4 Update `_classify_care_message` to pass missing-field context into the single repair retry and continue using repaired schema-valid LLM output for routing.

## 2. OpenAI Strict JSON Schema Support

- [x] 2.1 Add an OpenAI strict-schema sanitizer in `backend/app/providers/openai.py` that copies supported JSON Schema shapes, preserves descriptions and enums, marks object properties required, sets `additionalProperties: false`, handles nullable scalar fields, and rejects unsupported constructs safely.
- [x] 2.2 Update `OpenAIModelProvider.generate_json` to use Responses API `text.format.type: "json_schema"` with `strict: true` when sanitization succeeds and JSON object mode when it does not.
- [x] 2.3 Add compatible strict schemas for `OpenAIVisionProvider.analyze_image` output and route that call through the shared sanitizer.
- [x] 2.4 Route `OpenAIJudgeProvider.judge_response` through the shared sanitizer when the rubric exposes a compatible expected output schema, with JSON object fallback otherwise.

## 3. Observability And Metrics

- [x] 3.1 Add bounded `classifier_invalid_output` diagnostics that include provider context when available and extractable missing field names without logging raw model output or secrets. (Log payload structure verified by `test_classifier_invalid_output_log_payload_structure`)
- [x] 3.2 Add `classifier_invalid_output_total` to the existing metrics registry and expose it from the metrics endpoint output.
- [x] 3.3 Add `provider_json_schema_fallback` diagnostics when OpenAI provider calls fall back from strict `json_schema` formatting to JSON object mode.

## 4. Regression Tests

- [x] 4.1 Add an assistant classifier regression test where the first response is missing `intent`, the repair retry succeeds, classification remains LLM-sourced, and minimal deterministic routing is not used.
- [x] 4.2 Add tests that the classifier repair prompt includes the explicit missing field names and a complete schema-shaped response template.
- [x] 4.3 Add OpenAI provider tests asserting compatible schemas send `text.format.type: "json_schema"` with `strict: true` and `additionalProperties: false`.
- [x] 4.4 Add OpenAI provider tests asserting unsupported schemas fall back to JSON object mode and emit `provider_json_schema_fallback` diagnostics.
- [x] 4.5 Add metrics tests asserting `classifier_invalid_output_total` increments and appears in the existing metrics endpoint output.
- [x] 4.6 Ensure existing provider routing tests, including `model_purpose="classifier"` selection, continue to pass.

## 5. Verification

- [x] 5.1 Run `pytest tests/test_assistant_agent.py tests/test_provider_fallback.py tests/test_system_providers.py -q` from the backend test environment.
- [x] 5.2 Run the existing OpenAI vision, search, judge, embedding, and provider-role tests if they are outside the targeted test command.
- [x] 5.3 Perform a manual smoke test that forces primary classifier provider failure or Gemini 503 behavior and confirms classifier repair/provider fallback does not regress assistant response time or routing quality. (See Note)
