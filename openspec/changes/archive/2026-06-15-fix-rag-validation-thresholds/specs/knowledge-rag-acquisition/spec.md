## MODIFIED Requirements

### Requirement: Aspect-aware evidence validation

Runtime botanical evidence retrieval and fallback evidence acquisition SHALL validate evidence against the requested plant-care `required_aspects` before the evidence can be treated as answerable. Validation SHALL use semantic judging as the authority for aspect coverage and SHALL return answerability status, covered aspects, missing aspects, source support, contradictions, reason and confidence. The system MUST structurally validate judge output and degrade incoherent results to a safer status before answer synthesis or persistence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the judge result.

#### Scenario: Strong full-support non-safety evidence accepted with lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the evidence is treated as sufficient for the requested aspects

#### Scenario: Safety-sensitive aspect requires strict threshold

- **WHEN** the requested aspect is safety-sensitive, including pet toxicity or human edibility
- **THEN** validation requires direct evidence and the configured safety-sensitive threshold (default 0.85) before marking the aspect covered

#### Scenario: Generic care evidence fails specific aspect validation

- **WHEN** retrieved RAG evidence contains generic plant-care information but does not directly cover the requested watering frequency aspect
- **THEN** evidence validation does not mark `watering_frequency_or_trigger` as covered
- **AND** the evidence is not treated as full for that aspect

#### Scenario: Covered aspects constrained to request

- **WHEN** evidence validation returns covered aspects
- **THEN** every covered aspect is a subset of the requested `required_aspects`

#### Scenario: Missing aspects make evidence partial

- **WHEN** validation covers only some requested required aspects
- **THEN** the validation result marks the uncovered requested aspects as missing
- **AND** the validation result uses `status: "partial"`

#### Scenario: Low-confidence validation rejected

- **WHEN** validation confidence is below the configured evidence validation threshold for non-strong, non-safety results
- **THEN** the evidence is treated as insufficient for the requested aspects

#### Scenario: Deterministic keyword mismatch does not block semantic support

- **WHEN** semantic judging validates a requested aspect with coherent source support
- **AND** hardcoded keyword matching would fail because of language, synonyms, spelling variants or source phrasing
- **THEN** deterministic keyword mismatch does not reject the evidence as a blocking decision

#### Scenario: Incoherent full result degrades

- **WHEN** judge output declares `status: "full"` but omits required aspect coverage, source support, or adequate confidence
- **THEN** the system degrades the status to `partial` or `insufficient`
- **AND** the degraded result is not persisted unless source support remains structurally valid

#### Scenario: Contradictory result requires source evidence

- **WHEN** judge output declares `status: "contradictory"`
- **THEN** contradictions include source URLs for conflicting claims
- **AND** missing contradiction source URLs degrade the result to `insufficient`
