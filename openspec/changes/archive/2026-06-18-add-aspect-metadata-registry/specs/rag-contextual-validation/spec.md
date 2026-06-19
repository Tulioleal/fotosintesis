## MODIFIED Requirements

### Requirement: Context-aware evidence validation thresholds
The assistant SHALL use context-aware validation thresholds when evaluating evidence against required aspects. The threshold selection SHALL depend on metadata-defined aspect safety sensitivity and the structural strength of the judge result.

#### Scenario: Strong full-support non-safety aspect uses lower threshold
- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and the aspect metadata does not mark the aspect as safety-sensitive
- **THEN** the validation uses `assistant_strong_answer_validation_threshold` (default 0.30) instead of the default evidence validation threshold

#### Scenario: Safety-sensitive aspect uses strict threshold
- **WHEN** the requested aspect metadata marks the aspect as safety-sensitive
- **THEN** the validation uses `assistant_safety_validation_threshold` (default 0.85) regardless of structural strength

#### Scenario: Partial or ambiguous result uses default threshold
- **WHEN** the answerability judge does not meet all structural strength criteria (status not full, or not answerable, or missing aspects, or empty source support, or contradictions present)
- **THEN** the validation uses `assistant_evidence_validation_threshold` (default 0.75)

#### Scenario: Missing metadata uses non-safety fallback
- **WHEN** metadata is missing for a requested aspect
- **THEN** threshold selection treats the aspect as non-safety-sensitive unless another safety policy explicitly applies
- **AND** validation does not crash
