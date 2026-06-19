## Purpose

TBD - Defines context-aware validation thresholds for RAG evidence evaluation based on aspect safety sensitivity and structural strength of judge results.

## Requirements

### Requirement: Context-aware evidence validation thresholds

The assistant SHALL use context-aware validation thresholds when evaluating evidence against required aspects. The threshold selection SHALL depend on the aspect's safety sensitivity and the structural strength of the judge result. Safety-sensitive detection MUST use the expanded domain-qualified taxonomy and MUST NOT depend on legacy generic names.

#### Scenario: Strong full-support non-safety aspect uses lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and the aspect is not safety-sensitive
- **THEN** the validation uses `assistant_strong_answer_validation_threshold` (default 0.30) instead of the default evidence validation threshold

#### Scenario: Safety-sensitive aspect uses strict threshold

- **WHEN** the requested aspect is `toxicity_pet_safety`, `toxicity_human_edibility`, `toxicity_child_safety`, `toxicity_skin_irritation_risk`, `toxicity_ingestion_symptoms`, `toxicity_handling_precautions`, `safety_chemical_treatment_precautions`, `safety_disposal_precautions`, `safety_cross_contamination_prevention`, or `safety_when_to_contact_vet_or_poison_control`
- **THEN** the validation uses `assistant_safety_validation_threshold` (default 0.85) regardless of structural strength

#### Scenario: Partial or ambiguous result uses default threshold

- **WHEN** the answerability judge does not meet all structural strength criteria (status not full, or not answerable, or missing aspects, or empty source support, or contradictions present)
- **THEN** the validation uses `assistant_evidence_validation_threshold` (default 0.75)

#### Scenario: Missing metadata uses non-safety fallback

- **WHEN** metadata is missing for a requested aspect
- **THEN** threshold selection treats the aspect as non-safety-sensitive unless another safety policy explicitly applies
- **AND** validation does not crash

### Requirement: Strong full-support detection

The assistant SHALL detect structurally strong judge results using the following criteria:
- `status == "full"`
- `answerable == True`
- All requested aspects are in `covered_aspects`
- `source_support` is non-empty
- `contradictions` is empty

#### Scenario: All criteria met

- **WHEN** the judge result has `status: "full"`, `answerable: true`, all requested aspects covered, non-empty `source_support`, and empty `contradictions`
- **THEN** the result is classified as structurally strong

#### Scenario: Missing source support

- **WHEN** the judge result has `status: "full"` and `answerable: true` but `source_support` is empty
- **THEN** the result is not classified as structurally strong

#### Scenario: Contradictions present

- **WHEN** the judge result has `status: "full"` and `answerable: true` but `contradictions` is non-empty
- **THEN** the result is not classified as structurally strong

### Requirement: Configurable timeout for answerability judge

The assistant SHALL enforce a configurable timeout on answerability judge calls. The timeout SHALL be read from `assistant_judge_timeout_seconds` in settings.

#### Scenario: Judge completes within timeout

- **WHEN** the answerability judge responds within `assistant_judge_timeout_seconds`
- **THEN** the result is returned normally

#### Scenario: Judge exceeds timeout

- **WHEN** the answerability judge does not respond within `assistant_judge_timeout_seconds`
- **THEN** the assistant returns an `AnswerabilityResult` with `status: "insufficient"` and a reason containing "timed out"
- **AND** the request does not hang

### Requirement: Configurable timeout for web search

The assistant SHALL enforce a configurable timeout on trusted web search calls. The timeout SHALL be read from `assistant_web_search_timeout_seconds` in settings.

#### Scenario: Web search completes within timeout

- **WHEN** the trusted web search responds within `assistant_web_search_timeout_seconds`
- **THEN** the result is returned normally

#### Scenario: Web search exceeds timeout

- **WHEN** the trusted web search does not respond within `assistant_web_search_timeout_seconds`
- **THEN** the assistant records a tool failure with "timed out" reason
- **AND** the request completes with fallback reasons preserved

### Requirement: Strong threshold settings

The backend SHALL expose the following settings with default values:
- `assistant_strong_answer_validation_threshold: float = 0.30`
- `assistant_judge_timeout_seconds: float = 25.0`
- `assistant_web_search_timeout_seconds: float = 20.0`

#### Scenario: Default strong threshold

- **WHEN** no custom value is provided for `assistant_strong_answer_validation_threshold`
- **THEN** the system uses 0.30

#### Scenario: Default judge timeout

- **WHEN** no custom value is provided for `assistant_judge_timeout_seconds`
- **THEN** the system uses 25.0 seconds

#### Scenario: Default web search timeout

- **WHEN** no custom value is provided for `assistant_web_search_timeout_seconds`
- **THEN** the system uses 20.0 seconds
