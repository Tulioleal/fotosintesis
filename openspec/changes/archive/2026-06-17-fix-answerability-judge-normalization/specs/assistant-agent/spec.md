## MODIFIED Requirements

### Requirement: Aspect-gated care answer synthesis

The assistant SHALL validate local and web evidence against the requested `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST NOT blend verified claims and general guidance in the same sentence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity and structural strength of the normalized judge result. The normalized judge result MUST use only canonical requested aspect identifiers in `covered_aspects` and `missing_aspects`; explanatory judge text MUST remain in reason fields and MUST NOT be used as a missing aspect.

#### Scenario: Complete aspect coverage answers directly

- **WHEN** validated evidence covers every requested required aspect above the configured threshold
- **THEN** the assistant answers directly in `answer_language` using the validated evidence and source metadata without mentioning internal validation steps

#### Scenario: Complete partial judge coverage normalizes to full

- **WHEN** the answerability judge returns `status: "partial"` with valid source support for every requested required aspect
- **AND** the normalized covered aspects include every requested required aspect
- **AND** the result has no source-supported contradictions
- **THEN** the assistant treats the normalized result as `status: "full"` and `answerable: true`
- **AND** the assistant records no missing aspects for that answerability result

#### Scenario: Strong full-support non-safety answer accepted with lower threshold

- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the assistant treats the evidence as sufficient and answers from RAG without triggering web fallback

#### Scenario: Safety-sensitive aspect requires strict threshold

- **WHEN** a requested aspect is `pet_toxicity` or `human_edibility`
- **THEN** validation requires the aspect confidence to be above `assistant_safety_validation_threshold` (default 0.85) before marking the aspect covered

#### Scenario: Partial non-critical coverage answers covered aspects

- **WHEN** validated evidence covers at least one requested non-critical required aspect but leaves other non-critical aspects missing
- **THEN** the assistant answers the source-supported parts
- **AND** briefly states which requested aspects could not be source-validated
- **AND** any conservative general guidance for missing aspects is clearly labeled as general and not validated for the specific plant/question

#### Scenario: True partial coverage remains partial

- **WHEN** the answerability judge returns source-supported coverage for some but not all requested non-critical required aspects
- **THEN** the assistant preserves `status: "partial"` and `answerable: false`
- **AND** the assistant computes missing aspects from requested aspects that are not covered after normalization

#### Scenario: No validated coverage returns transparent insufficient answer

- **WHEN** no requested required aspects are covered by validated evidence
- **THEN** the assistant states that source-backed evidence was insufficient for the specific plant/question
- **AND** any conservative general guidance is clearly labeled as general and not source-validated for the specific plant/question
- **AND** the assistant does not cite general guidance as source-backed evidence

#### Scenario: Safety-sensitive missing evidence returns conservative guidance

- **WHEN** a safety-sensitive care question lacks direct validated evidence for the primary safety aspect at the configured safety-sensitive threshold
- **THEN** the assistant states that direct source-backed evidence was unavailable for the specific plant/question
- **AND** the assistant may provide conservative safety guidance labeled as general and not source-validated
- **AND** the assistant does not claim the plant is safe, toxic, edible, or consumable without direct evidence

#### Scenario: Contradictory evidence is presented without definitive claim

- **WHEN** final evidence validation reports contradictory source-supported claims for a requested aspect
- **THEN** the assistant states that the sources conflict
- **AND** the assistant shows source links in the text for the conflicting claims
- **AND** the assistant avoids a definitive recommendation from the contradictory evidence

### Requirement: Care answer diagnostic metadata

The assistant response SHALL expose bounded diagnostic metadata for plant-care answers including `intent`, `topic`, `required_aspects`, `covered_aspects`, `missing_aspects`, `evidence_path`, and `answer_language`. The response MUST NOT expose prompts, raw model reasoning, raw full evidence text, or internal provider errors beyond existing tool failure metadata. Diagnostic `covered_aspects` and `missing_aspects` MUST contain only canonical requested aspect identifiers after answerability normalization.

#### Scenario: Diagnostics included for grounded answer

- **WHEN** the assistant returns a plant-care answer from validated evidence
- **THEN** the response metadata includes intent, topic, requested aspects, covered aspects, missing aspects, evidence path, and answer language

#### Scenario: Diagnostics exclude malformed missing-aspect explanations

- **WHEN** the answerability judge returns explanatory text in `missing_aspects` or omits missing aspects while providing reasons
- **THEN** the assistant excludes that explanatory text from diagnostic `missing_aspects`
- **AND** diagnostic missing aspects contain only uncovered requested aspect identifiers

#### Scenario: Internal details are not exposed

- **WHEN** the assistant response includes diagnostic metadata
- **THEN** the metadata excludes prompts, raw model reasoning, raw full evidence text, and provider internals except existing tool failure summaries
