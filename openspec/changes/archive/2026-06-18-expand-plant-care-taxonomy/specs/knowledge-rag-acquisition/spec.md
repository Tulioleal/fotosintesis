## MODIFIED Requirements

### Requirement: Aspect-aware evidence validation

Runtime botanical evidence retrieval and fallback evidence acquisition SHALL validate evidence against the requested plant-care domain-qualified `required_aspects` before the evidence can be treated as answerable. Validation SHALL use semantic judging as the authority for aspect coverage and SHALL return answerability status, covered aspects, missing aspects, source support, contradictions, reason and confidence. The system MUST structurally validate judge output and degrade incoherent results to a safer status before answer synthesis or persistence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity, evidence source type and structural strength of the normalized judge result. For non-safety assistant web fallback evidence, validation confidence SHALL be informational and SHALL NOT be the sole reason to reject direct source-supported requested-aspect coverage. Normalized validation results MUST constrain `covered_aspects` and `missing_aspects` to canonical requested aspect identifiers and MUST NOT copy free-form judge reasons into aspect arrays. Validation MUST NOT infer an aspect domain from `CareTopic` when judging coverage.

#### Scenario: Strong full-support non-safety evidence accepted with lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the evidence is treated as sufficient for the requested aspects

#### Scenario: Complete partial result is promoted after normalization

- **WHEN** the answerability judge returns `status: "partial"` with valid source support for every requested required aspect
- **AND** normalized covered aspects include every requested required aspect
- **AND** normalized missing aspects are empty
- **AND** no contradictions are present
- **THEN** the validation result uses `status: "full"`
- **AND** the validation result uses `answerable: true`

#### Scenario: Safety-sensitive aspect requires strict threshold

- **WHEN** the requested aspect is safety-sensitive, including `toxicity_pet_safety`, `toxicity_human_edibility`, `toxicity_child_safety`, `toxicity_skin_irritation_risk`, `toxicity_ingestion_symptoms`, `toxicity_handling_precautions`, or applicable `safety_*` treatment, disposal, cross-contamination, vet, or poison-control aspects
- **THEN** validation requires direct evidence and the configured safety-sensitive threshold (default 0.85) before marking the aspect covered

#### Scenario: Generic care evidence fails specific aspect validation

- **WHEN** retrieved RAG evidence contains generic plant-care information but does not directly cover the requested watering frequency aspect
- **THEN** evidence validation does not mark `watering_frequency_or_trigger` as covered
- **AND** the evidence is not treated as full for that aspect

#### Scenario: Domain-qualified aspect cannot be covered by sibling domain evidence

- **WHEN** requested aspects include `pest_treatment_action`
- **AND** evidence only discusses disease treatment or generic treatment steps
- **THEN** evidence validation does not mark `pest_treatment_action` as covered

#### Scenario: Covered aspects constrained to request

- **WHEN** evidence validation returns covered aspects
- **THEN** every covered aspect is a subset of the requested `required_aspects`

#### Scenario: Missing aspects constrained to request

- **WHEN** evidence validation returns missing aspects
- **THEN** every missing aspect is a subset of the requested `required_aspects`
- **AND** missing aspects do not contain explanations, reason strings, or unrequested aspect identifiers

#### Scenario: Missing aspects make evidence partial

- **WHEN** validation covers only some requested required aspects
- **THEN** the validation result marks the uncovered requested aspects as missing
- **AND** the validation result uses `status: "partial"`

#### Scenario: Low-confidence validation rejected for non-web evidence

- **WHEN** non-web validation confidence is below the configured evidence validation threshold for non-strong, non-safety results
- **THEN** the evidence is treated as insufficient for the requested aspects

#### Scenario: Low-confidence web validation remains usable when directly supported

- **WHEN** assistant web fallback evidence has direct source support for requested non-safety aspects and no contradictions
- **AND** validation confidence is below the configured evidence validation threshold
- **THEN** the evidence can still be treated as answerable for those source-supported aspects
- **AND** validation confidence is retained as informational metadata

#### Scenario: Deterministic keyword mismatch does not block semantic support

- **WHEN** semantic judging validates a requested aspect with coherent source support
- **AND** hardcoded keyword matching would fail because of language, synonyms, spelling variants or source phrasing
- **THEN** deterministic keyword mismatch does not reject the evidence as a blocking decision

#### Scenario: Incoherent full result degrades

- **WHEN** judge output declares `status: "full"` but omits required aspect coverage, source support, or adequate confidence for evidence types where confidence remains a hard gate
- **THEN** the system degrades the status to `partial` or `insufficient`
- **AND** the degraded result is not persisted unless source support remains structurally valid

#### Scenario: Contradictory result requires source evidence

- **WHEN** judge output declares `status: "contradictory"`
- **THEN** contradictions include source URLs for conflicting claims
- **AND** missing contradiction source URLs degrade the result to `insufficient`

### Requirement: Targeted missing-aspect web fallback

Trusted web fallback for assistant plant-care answers SHALL run after local evidence validation fails to return `full`. Web search SHALL use confirmed taxonomy, topic, domain-qualified required aspects, and the original user question, and SHALL exclude nicknames, display names, and classifier plant references from search construction. Query construction SHALL convert selected domain-qualified aspects into useful natural-language terms and MUST NOT depend on `CareTopic` to disambiguate the aspect domain. This change SHALL keep the current single-search strategy and SHALL NOT add per-aspect query expansion.

#### Scenario: RAG covers no requested aspects

- **WHEN** local RAG validation covers none of the requested required aspects
- **THEN** trusted web fallback searches for all requested required aspects using confirmed taxonomy and the original user question

#### Scenario: RAG covers some requested aspects

- **WHEN** local RAG validation covers some requested required aspects and leaves others missing
- **THEN** trusted web fallback searches using confirmed taxonomy, missing aspects, and the original user question before final answer synthesis

#### Scenario: RAG contradictory triggers web fallback

- **WHEN** local RAG validation reports contradictory evidence for requested required aspects
- **THEN** trusted web fallback searches for the affected aspects using confirmed taxonomy and the original user question

#### Scenario: Search query excludes display name

- **WHEN** the display plant name differs from confirmed taxonomy
- **THEN** trusted web fallback query construction uses `plant_binomial_name` or `plant_scientific_name` and does not use the display name, nickname, apodo, or classifier plant reference

#### Scenario: Domain-qualified aspect terms are used

- **WHEN** missing aspects include `propagation_rooting_conditions`, `nutrition_deficiency_signs`, or `toxicity_pet_safety`
- **THEN** trusted web fallback query construction includes natural-language terms for propagation rooting conditions, nutrition deficiency signs, or pet toxicity safety respectively

#### Scenario: Web fallback skipped when local evidence complete

- **WHEN** local evidence validation covers all requested required aspects above threshold with `status: "full"`
- **THEN** trusted web fallback is not called for that answer

#### Scenario: Per-aspect query expansion unchanged

- **WHEN** this change is implemented
- **THEN** web fallback does not add new per-aspect query expansion rules as part of this change
