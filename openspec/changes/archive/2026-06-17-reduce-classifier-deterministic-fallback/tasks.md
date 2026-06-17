## 1. Classifier Contract

- [x] 1.1 Add a top-level `required` list to `CARE_CLASSIFIER_SCHEMA` covering all fields required by `CareClassification`.
- [x] 1.2 Add field descriptions for `confidence`, `required_aspects`, `plant_reference`, and `needs_retrieval` to reduce provider omissions.
- [x] 1.3 Strengthen `_care_classifier_prompt` so it explicitly instructs the model to include every schema field, use `null` for absent `plant_reference`, and always include numeric `confidence`.

## 2. Classifier Retry And Fallback Logic

- [x] 2.1 Refactor `_classify_care_message` so recoverable invalid classifier outputs can be retried once before deterministic fallback.
- [x] 2.2 Add a stricter repair prompt path for the retry that preserves the original user message and confirmed taxonomy context.
- [x] 2.3 Ensure provider timeouts and provider exceptions still skip retry and fall back deterministically with existing failure metadata.
- [x] 2.4 Ensure invalid output after retry falls back deterministically and records a classifier validation failure.

## 3. Low-Confidence Handling

- [x] 3.1 Change low-confidence valid classifier output from hard fallback to accepted LLM routing.
- [x] 3.2 Keep `assistant_classification_accept_threshold` as a diagnostic threshold and avoid appending low confidence to `tool_failures`.
- [x] 3.3 Preserve classifier source, confidence, and fallback reason logging so accepted low-confidence results remain observable.

## 4. Tests

- [x] 4.1 Update the existing low-confidence classifier test to assert valid LLM output is used instead of deterministic fallback.
- [x] 4.2 Add a test where missing `confidence` on the first classifier response is repaired by the retry and the LLM classification is used.
- [x] 4.3 Add a test where invalid classifier output remains invalid after retry and deterministic fallback is used.
- [x] 4.4 Add a test asserting `CARE_CLASSIFIER_SCHEMA` requires `confidence` and the other `CareClassification` fields.
- [x] 4.5 Run the focused assistant-agent test suite and fix any regressions.

## 5. Verification

- [x] 5.1 Manually inspect logs or test diagnostics to confirm repaired classifier output does not produce `assistant_tool_failure` for successful requests.
- [x] 5.2 Run broader backend tests if focused assistant tests pass.
