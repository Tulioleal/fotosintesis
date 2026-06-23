## ADDED Requirements

### Requirement: OpenAI strict JSON outputs

OpenAI-backed model, vision, and judge provider roles SHALL request strict structured JSON outputs when the requested response shape can be represented as an OpenAI-compatible JSON schema. The provider SHALL preserve the internal provider interfaces and SHALL fall back to JSON object mode when no compatible schema is available or when a schema cannot be safely sanitized.

#### Scenario: OpenAI model JSON generation uses strict schema

- **WHEN** `OpenAIModelProvider.generate_json()` receives a compatible object schema
- **THEN** the OpenAI Responses API request uses `text.format.type: "json_schema"`
- **AND** the request sets `strict: true`, includes the sanitized schema, includes all schema properties in `required`, and sets `additionalProperties: false`

#### Scenario: OpenAI vision output uses strict schema

- **WHEN** `OpenAIVisionProvider.analyze_image()` requests JSON plant-image analysis output
- **THEN** the OpenAI Responses API request uses strict `json_schema` formatting for the expected description and candidate fields when that schema is compatible

#### Scenario: OpenAI judge output uses strict schema

- **WHEN** `OpenAIJudgeProvider.judge_response()` receives a rubric with a compatible expected JSON output shape
- **THEN** the OpenAI Responses API request uses strict `json_schema` formatting for the expected judge result

#### Scenario: Unsupported schema falls back safely

- **WHEN** an OpenAI JSON-capable provider role receives no schema or a schema that contains unsupported strict-mode constructs such as unresolved references or unsafe unions
- **THEN** the provider uses JSON object mode for that call
- **AND** the provider emits `provider_json_schema_fallback` diagnostics without logging secrets or raw credentials

### Requirement: Classifier invalid-output observability

The system SHALL expose bounded diagnostics for classifier invalid-output events so operators can distinguish provider availability failures from schema-validation failures that required repair or fallback.

#### Scenario: Missing classifier fields are logged

- **WHEN** classifier validation fails because required fields are missing
- **THEN** the system records `classifier_invalid_output` diagnostics with the provider, request correlation when available, and the bounded list of missing field names
- **AND** the diagnostic does not include raw credentials or unbounded model output

#### Scenario: Classifier invalid-output metric is exposed

- **WHEN** classifier validation fails before repair or after repair
- **THEN** the system increments `classifier_invalid_output_total`
- **AND** the existing metrics endpoint exposes the counter as part of the runtime metrics output
