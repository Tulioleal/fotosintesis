## Context

The assistant classifies plant-care messages before retrieval using `CARE_CLASSIFIER_SCHEMA` and validates the returned object with `CareClassification`. OpenAI currently uses Responses API JSON object mode for `generate_json`, `analyze_image`, and `judge_response`, so the provider only guarantees valid JSON syntax; it does not guarantee that required fields such as `intent` are present.

When classifier validation fails, the graph retries once with a repair prompt and then preserves the existing minimal deterministic fallback behavior. The repair prompt currently receives only a validation error string, which makes missing-field repair less direct than it needs to be.

OpenAI Responses API structured outputs support `text.format` with `type: "json_schema"` and `strict: true` for schema-constrained output. The strict format expects an object schema with explicit `required` entries and `additionalProperties: false`; unsupported or ambiguous schema shapes need a safe fallback path.

## Goals / Non-Goals

**Goals:**

- Prevent missing required classifier fields, especially `intent`, from causing avoidable fallback to minimal deterministic routing.
- Keep the current retry-once classifier repair policy and the existing deterministic fallback semantics after repair is exhausted.
- Use OpenAI strict structured outputs for JSON generation when the supplied schema can be safely converted to the supported strict subset.
- Reuse one OpenAI schema sanitization helper for model JSON generation, vision JSON output, and judge JSON output.
- Emit bounded diagnostics and metrics for classifier invalid-output events and OpenAI JSON schema fallback.

**Non-Goals:**

- Do not redesign the classifier or change `CareClassification` fields, enum values, or public API behavior.
- Do not add deterministic keyword, regex, translated-word, or language-specific semantic classification logic.
- Do not change RAG ingestion, answerability judging, retrieval eligibility, trusted-source policy, or model provider routing semantics.
- Do not require OpenAI strict structured outputs for callers that provide no schema or provide a schema that cannot be safely sanitized.

## Decisions

1. Use schema validation metadata to guide repair, not semantic heuristics.

   The classifier path will parse validation errors to extract missing field names and pass those names into `_care_classifier_repair_prompt`. This is deterministic schema-error handling only; it does not infer botanical meaning. The repair prompt will also include a complete response template and instruct the model not to remove fields already present in the previous response.

   Alternative considered: let Pydantic error strings remain the only repair context. That keeps code smaller but fails to directly tell the model which required fields are absent.

2. Keep one repair attempt and preserve fallback semantics.

   The graph will continue to ignore invalid classifier output for routing, retry once while the provider is available, and fall back only if the retry is unavailable or still structurally invalid. A successful repaired LLM response remains `source: "llm"`.

   Alternative considered: add multiple repair retries. That could improve recovery but increases latency and cost for the exact path this change is trying to reduce.

3. Prefer OpenAI strict `json_schema` formatting when schema-compatible.

   `OpenAIModelProvider.generate_json` will build a `text.format` object using `type: "json_schema"`, `name`, sanitized `schema`, and `strict: True` when the caller supplies a compatible schema. Unsupported schemas fall back to `type: "json_object"` and emit `provider_json_schema_fallback` diagnostics.

   Alternative considered: keep JSON object mode and rely only on prompt changes. That is lower risk but does not address the provider-level root cause because JSON object mode does not enforce required fields.

4. Centralize strict-schema sanitization in `backend/app/providers/openai.py`.

   A helper such as `_to_openai_strict_schema(schema)` will copy and normalize supported JSON Schema shapes, ensure object properties are all required, set `additionalProperties: false` on object schemas, preserve descriptions and enums, and handle nullable scalar fields from existing schema forms. The helper will reject or decline unsupported shapes such as `$ref`, `oneOf`, or non-trivial `anyOf` branches rather than silently weakening validation.

   Alternative considered: hand-write separate schemas for classifier, judge, and vision. That would duplicate rules and increase drift between provider calls.

5. Use explicit built-in schemas for OpenAI vision and judge output where needed.

   `generate_json` already receives a schema from callers. `analyze_image` and `judge_response` currently rely on prompt-only JSON structures, so they need local schema construction or a rubric-derived schema before strict mode can be used. If a judge rubric does not provide a sanitizable expected output schema, the provider will fall back to JSON object mode with diagnostics.

   Alternative considered: change only `generate_json`. That would fix the classifier root cause but leave two nearby OpenAI JSON paths with weaker guarantees and duplicate future work.

## Risks / Trade-offs

- OpenAI strict mode rejects a schema shape used by an existing caller -> The sanitizer falls back to JSON object mode and logs `provider_json_schema_fallback` with provider role, operation, and schema name when available.
- Sanitization accidentally weakens caller validation -> Unsupported constructs are rejected instead of rewritten unless the conversion preserves equivalent validation, and downstream Pydantic/domain validation remains authoritative.
- Prompt tightening changes classifier behavior beyond structural repair -> Keep examples focused on schema completeness and existing canonical fields; do not introduce new semantic keyword rules.
- Metrics cardinality grows from missing field labels -> Track a bounded counter for invalid classifier output and log missing field names; avoid unbounded Prometheus labels derived from raw model output or user text.
- Strict structured outputs add provider-side validation latency -> Use the existing single provider call path and measure through existing provider-call metrics; JSON object fallback remains available.

## Migration Plan

- Implement prompt and repair improvements first so missing-field retries improve even when a provider falls back to JSON object mode.
- Add the OpenAI strict-schema helper and switch compatible JSON calls to `json_schema` formatting with JSON object fallback.
- Add tests for missing `intent` repair, strict `json_schema` selection, fallback logging, and metrics exposure.
- Roll back by reverting the provider format selection to JSON object mode while keeping classifier repair improvements if strict mode exposes provider incompatibility.

## Open Questions

- Should OpenAI strict structured outputs be guarded by a runtime flag, or is per-call JSON object fallback sufficient for rollout?
- Which judge rubric schema fields, if any, should be treated as authoritative when constructing strict judge output schemas?
