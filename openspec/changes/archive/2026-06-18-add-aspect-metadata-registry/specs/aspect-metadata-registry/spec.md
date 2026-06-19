## ADDED Requirements

### Requirement: Required aspect metadata registry
The backend SHALL provide a centralized registry keyed by `RequiredAspect` that defines structured metadata for aspect semantics. Each registry entry MUST include `domain`, `label`, `query_label`, and `search_terms`, and MAY include `coverage_guidance`, `safety_sensitive`, and `diagnostic_label`. The registry MUST NOT include deterministic evidence keywords or any field whose purpose is to decide whether evidence covers an aspect.

#### Scenario: Metadata exists for representative aspects
- **WHEN** metadata is requested for `watering_frequency_or_trigger`, a non-guided care aspect such as `soil_drainage`, and a safety-sensitive aspect such as `toxicity_pet_safety`
- **THEN** the registry returns structured metadata for each aspect
- **AND** each returned entry includes domain, label, query label, and search terms

#### Scenario: Coverage guidance is optional
- **WHEN** metadata is requested for an aspect whose enum name is sufficient for evidence coverage, such as `soil_drainage`
- **THEN** the returned metadata may omit `coverage_guidance`
- **AND** callers do not synthesize generic guidance for that aspect

#### Scenario: Safety-sensitive metadata is explicit
- **WHEN** metadata is requested for an aspect involving toxicity, poison-control escalation, chemical-treatment precautions, disposal precautions, or cross-contamination prevention
- **THEN** the metadata marks the aspect as safety-sensitive

### Requirement: No deterministic evidence coverage gates
The backend MUST NOT use deterministic keyword matching, token presence checks, or any other string-based heuristic to decide whether evidence covers a required aspect. The answerability judge is the sole authority for determining evidence coverage. Snippet and content eligibility gates MUST be limited to non-semantic checks such as valid URL, trusted source selection, and non-empty text presence.

#### Scenario: Non-English snippet reaches the judge
- **WHEN** a trusted web search returns a snippet in Spanish, Italian, or another non-English language
- **AND** the snippet contains no English keywords related to the requested aspect
- **THEN** the snippet is still passed to the answerability judge for coverage evaluation
- **AND** the judge may determine coverage based on semantic understanding of the non-English text

#### Scenario: Snippet-only evidence eligible without keyword match
- **WHEN** a trusted search result has a non-empty snippet but no fetched page content
- **AND** the snippet text does not contain any predefined keywords for the requested aspect
- **THEN** the result is still included as eligible snippet-only evidence
- **AND** the answerability judge decides whether the snippet covers the requested aspect

### Requirement: Metadata lookup helpers
The backend SHALL expose helper functions for looking up metadata, query terms, validation guidance, and safety sensitivity from `RequiredAspect` values or canonical aspect strings. Helper functions MUST fall back safely when metadata is missing or the aspect string is unknown.

#### Scenario: Metadata lookup accepts enum or string
- **WHEN** `metadata_for_aspect` receives a `RequiredAspect` member or its canonical string value
- **THEN** it returns the same metadata entry

#### Scenario: Unknown aspect does not crash
- **WHEN** a metadata helper receives an unknown aspect string
- **THEN** it returns an empty, false, or fallback result appropriate to that helper
- **AND** the assistant pipeline continues without raising an exception

#### Scenario: Query terms use metadata first
- **WHEN** query terms are requested for aspects with metadata-defined query labels or search terms
- **THEN** the helper returns human-readable metadata-derived terms
- **AND** duplicate terms are removed while preserving useful order

#### Scenario: Validation guidance returns only configured guidance
- **WHEN** validation guidance is requested for a mixed list containing aspects with and without `coverage_guidance`
- **THEN** the helper returns guidance only for aspects whose metadata defines `coverage_guidance`
- **AND** the returned keys remain canonical aspect strings

### Requirement: Canonical aspect identifiers remain authoritative
The metadata registry SHALL describe aspect semantics without replacing canonical `RequiredAspect` enum values in classifier contracts, answerability normalization, or public assistant diagnostic fields.

#### Scenario: Metadata labels do not replace enum values
- **WHEN** metadata provides a human-readable label or diagnostic label for an aspect
- **THEN** classifier output, judge `covered_aspects`, judge `missing_aspects`, and assistant diagnostics continue to use canonical enum strings for aspect identifiers
- **AND** any readable labels are exposed only as additional metadata where supported
