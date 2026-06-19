## ADDED Requirements

### Requirement: Metadata-driven aspect semantics
The assistant plant-care pipeline SHALL consume the centralized aspect metadata registry for answerability guidance, targeted web fallback query construction, safety-sensitive routing checks where practical, and readable diagnostic labels where exposed. Canonical `RequiredAspect` values MUST remain the authoritative identifiers for classifier output, judge normalization, and existing diagnostic arrays.

#### Scenario: Judge receives configured coverage guidance
- **WHEN** the assistant asks the answerability judge to evaluate evidence for requested aspects that define metadata `coverage_guidance`
- **THEN** the judge payload includes guidance for those requested aspects keyed by canonical aspect string
- **AND** the payload does not include guidance for requested aspects whose metadata omits `coverage_guidance`

#### Scenario: Watering trigger evidence remains covered
- **WHEN** the requested aspect is `watering_frequency_or_trigger`
- **AND** supplied evidence recommends watering based on a soil-moisture trigger such as letting the top layer or substrate dry
- **THEN** the metadata-provided guidance allows the judge to treat that evidence as directly covering the watering aspect even without a calendar interval

#### Scenario: Diagnosis guidance rejects unrelated general care
- **WHEN** the requested aspect is a diagnosis aspect with metadata `coverage_guidance`
- **AND** supplied evidence only contains general care information without explicitly connecting evidence to the symptom or diagnosis requested
- **THEN** the assistant guidance tells the judge to treat the aspect as missing

#### Scenario: Web fallback query uses aspect metadata
- **WHEN** the assistant builds a trusted web fallback query for missing required aspects with metadata-defined query labels or search terms
- **THEN** the query includes metadata-derived human-readable aspect terms instead of relying only on raw enum names with underscores replaced
- **AND** the query still includes confirmed scientific plant context and the user's question context

#### Scenario: Snippet eligibility is non-semantic
- **WHEN** the assistant evaluates whether a trusted web snippet or fetched content is eligible for judge evaluation
- **THEN** eligibility is determined only by non-semantic checks: valid URL, trusted source, non-empty text
- **AND** deterministic keyword matching is NOT used to decide whether evidence covers an aspect

#### Scenario: Safety checks use metadata
- **WHEN** fallback or validation logic needs to know whether a requested or missing aspect is safety-sensitive
- **THEN** it uses aspect metadata safety sensitivity where practical instead of a separate hardcoded aspect set

#### Scenario: Diagnostics preserve canonical aspect values
- **WHEN** assistant response diagnostics include required, covered, or missing aspects
- **THEN** those arrays contain canonical aspect strings after normalization
- **AND** any readable labels derived from metadata are additional diagnostic information and do not replace canonical values

#### Scenario: Missing metadata falls back safely
- **WHEN** the assistant receives an unknown aspect string or an aspect without a registry entry in a fallback path
- **THEN** metadata consumers fall back to enum-derived labels, the original aspect string, or empty optional values as appropriate
- **AND** the assistant does not crash

## MODIFIED Requirements

### Requirement: Aspect-gated care answer synthesis
The assistant SHALL validate local and web evidence against the requested `required_aspects` before synthesizing a plant-care answer. Final care answers MUST distinguish source-validated claims from unsupported or general guidance, SHALL preserve the classified `answer_language`, and MUST NOT blend verified claims and general guidance in the same sentence. Validation SHALL use context-aware thresholds based on metadata-defined aspect safety sensitivity and structural strength of the normalized judge result. The normalized judge result MUST use only canonical requested aspect identifiers in `covered_aspects` and `missing_aspects`; explanatory judge text MUST remain in reason fields and MUST NOT be used as a missing aspect.

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
- **WHEN** the answerability judge returns `status: "full"`, `answerable: true`, all requested aspects are covered, `source_support` is non-empty, `contradictions` is empty, and no requested aspect is metadata-marked safety-sensitive
- **AND** the judge confidence is above `assistant_strong_answer_validation_threshold` (default 0.30)
- **THEN** the assistant treats the evidence as sufficient and answers from RAG without triggering web fallback

#### Scenario: Safety-sensitive aspect requires strict threshold
- **WHEN** any requested aspect is metadata-marked safety-sensitive
- **THEN** validation requires that aspect confidence to be above `assistant_safety_validation_threshold` (default 0.85) before marking the aspect covered

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
