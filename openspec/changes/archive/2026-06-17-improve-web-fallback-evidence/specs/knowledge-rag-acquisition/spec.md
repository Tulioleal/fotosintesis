## MODIFIED Requirements

### Requirement: Aspect-aware evidence validation

Runtime botanical evidence retrieval and fallback evidence acquisition SHALL validate evidence against the requested plant-care `required_aspects` before the evidence can be treated as answerable. Validation SHALL use semantic judging as the authority for aspect coverage and SHALL return answerability status, covered aspects, missing aspects, source support, contradictions, reason and confidence. The system MUST structurally validate judge output and degrade incoherent results to a safer status before answer synthesis or persistence. Validation SHALL use context-aware thresholds based on aspect safety sensitivity, evidence source type and structural strength of the judge result. For non-safety assistant web fallback evidence, validation confidence SHALL be informational and SHALL NOT be the sole reason to reject direct source-supported requested-aspect coverage.

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

Trusted web fallback for assistant plant-care answers SHALL run after local evidence validation fails to return `full`. Web search SHALL use confirmed taxonomy, topic, required aspects, and the original user question, and SHALL exclude nicknames, display names, and classifier plant references from search construction. This change SHALL keep the current query construction strategy and SHALL NOT add per-aspect query expansion.

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

#### Scenario: Web fallback skipped when local evidence complete

- **WHEN** local evidence validation covers all requested required aspects above threshold with `status: "full"`
- **THEN** trusted web fallback is not called for that answer

#### Scenario: Per-aspect query expansion unchanged

- **WHEN** this change is implemented
- **THEN** web fallback does not add new per-aspect query expansion rules as part of this change

## ADDED Requirements

### Requirement: Reusable acquisition search candidates

Runtime retrieval and acquisition SHALL expose same-request search candidates or fetched web evidence metadata when acquisition performs provider search, so assistant fallback can avoid redundant web searches. Reused candidates MUST preserve confirmed taxonomy, topic, requested aspects when available, source URL, source domain, snippet length, fetched content length when available, and trust validation status.

#### Scenario: Acquisition search candidates available to fallback
- **WHEN** knowledge acquisition performs a provider search during an assistant request
- **THEN** the acquisition result exposes candidate metadata or fetched evidence that assistant fallback can inspect for reuse

#### Scenario: Candidate reuse preserves trust status
- **WHEN** assistant fallback reuses acquisition search candidates
- **THEN** each reused candidate preserves whether it passed trusted-source validation or was selected as an external fallback candidate

#### Scenario: Duplicate search avoided
- **WHEN** reusable same-request candidates are sufficient for fallback evaluation
- **THEN** assistant fallback does not issue another provider search for the same confirmed taxonomy and requested aspects

### Requirement: Care-oriented trusted source selection

The trusted source configuration SHALL support adding and prioritizing care-oriented sources for practical plant-care fallback while continuing to distinguish taxonomy-oriented sources from care-oriented evidence. Adding more sources SHALL NOT bypass trusted-source validation, fetch limits, or answerability judging.

#### Scenario: Care-oriented source added
- **WHEN** a care-oriented approved domain is configured
- **THEN** trusted web fallback can select it as a candidate source while preserving existing trust validation

#### Scenario: Taxonomy-only evidence is insufficient for care question
- **WHEN** a trusted source contains taxonomy or distribution information but does not directly answer the requested care aspect
- **THEN** answerability validation treats it as insufficient for that care aspect

#### Scenario: More sources do not bypass validation
- **WHEN** additional approved domains are configured
- **THEN** selected evidence still requires direct requested-aspect coverage before it can support an assistant answer
