## MODIFIED Requirements

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
