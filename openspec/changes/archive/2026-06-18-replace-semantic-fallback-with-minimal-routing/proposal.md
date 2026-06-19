## Why

The current deterministic classifier fallback duplicates the LLM classifier by inferring detailed botanical care topics and required aspects from keyword rules. That parallel semantic classifier is brittle, hard to maintain as the taxonomy grows, and can produce incorrect `CareTopic` or `RequiredAspect` values when the primary LLM classifier is unavailable or invalid.

## What Changes

- Replace deterministic semantic botanical fallback classification with a minimal deterministic routing fallback.
- Preserve LLM classification, provider fallback, schema validation, and JSON repair as the only source of detailed botanical `topic` and `required_aspects` values.
- Keep deterministic fallback only for safe explicit routes: unsafe or injection input, reminder requests, light measurement requests, plant identification requests, obvious out-of-domain messages, and unknown plant-care requests.
- Represent plant-care fallback degradation as `plant_care_question_unknown`, using either `topic: "general_care"` with `required_aspects: ["general_care_summary"]` or a clarification response.
- Update diagnostics and logs so classifier failures distinguish timeout, invalid output, provider failure, and minimal routing fallback usage.
- Update tests so fallback paths no longer expect deterministic detailed watering, light, diagnosis, pest, repotting, toxicity, or other domain-qualified aspect inference.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: classifier fallback behavior changes from deterministic semantic classification to minimal deterministic routing after LLM classification, provider fallback, and repair fail.

## Impact

- Affected backend assistant classifier fallback logic and routing diagnostics.
- Affected tests that currently assert deterministic semantic care-topic or required-aspect inference.
- No dependency changes are expected.
- User experience may become more conservative during classifier outages because unknown plant-care fallback may ask a concise clarification or use general care summary instead of guessed specific care aspects.
