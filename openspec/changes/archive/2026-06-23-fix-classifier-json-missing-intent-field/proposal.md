## Why

The care-message classifier can return valid JSON that is still missing required classifier fields, most commonly `intent`, causing the graph to discard a near-complete LLM result and fall back to minimal deterministic routing. This lowers routing quality and adds latency because OpenAI JSON mode guarantees syntactic JSON but not schema compliance.

## What Changes

- Strengthen the care classifier prompt and repair prompt so required fields are explicit, complete examples are shown, and repair retries receive the exact missing field names.
- Update classifier invalid-output handling to extract missing fields from validation errors, log them, and retry once before preserving the existing deterministic fallback policy.
- Switch OpenAI JSON generation paths with compatible schemas from JSON object mode to Responses API structured outputs using strict `json_schema` formatting.
- Add an OpenAI schema sanitization path that preserves supported schema details, enforces strict-mode shape requirements, and falls back to JSON object mode with explicit diagnostics when a schema cannot be safely converted.
- Expose diagnostics for classifier invalid output and OpenAI structured-output fallback through existing logging and metrics surfaces.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Require repair retries for missing classifier fields to receive explicit missing-field context and use repaired schema-valid classifier output before falling back to minimal deterministic routing.
- `provider-observability`: Require OpenAI JSON-capable provider roles to use strict structured outputs when schema-compatible and to emit safe diagnostics when falling back to JSON object mode.

## Impact

- Affected backend graph code: `backend/app/assistant/graph.py` classifier schema, prompt, repair prompt, validation handling, diagnostics and metrics.
- Affected provider code: `backend/app/providers/openai.py` JSON generation, judge and vision structured response formatting, and strict-schema sanitization helper.
- Affected tests: assistant classifier regression tests, provider fallback tests, system provider tests, and OpenAI provider role tests.
- No public API changes, no classifier schema field changes, no RAG ingestion policy changes, and no change to deterministic fallback semantics after repair is exhausted.
