## ADDED Requirements

### Requirement: Aspect-aware evidence validation
Runtime botanical evidence retrieval and fallback evidence acquisition SHALL validate evidence against the requested plant-care `required_aspects` before the evidence can be treated as answerable. Validation SHALL combine LLM semantic validation with deterministic guardrails and SHALL return answerability, covered aspects, missing aspects, unsupported-claim risk, reason, and confidence.

#### Scenario: Generic care evidence fails specific aspect validation
- **WHEN** retrieved RAG evidence contains generic plant-care information but does not directly cover the requested watering frequency aspect
- **THEN** evidence validation does not mark `watering_frequency_or_trigger` as covered
- **AND** the evidence is not treated as fully answerable for that aspect

#### Scenario: Covered aspects constrained to request
- **WHEN** evidence validation returns covered aspects
- **THEN** every covered aspect is a subset of the requested `required_aspects`

#### Scenario: Missing aspects make evidence partially answerable
- **WHEN** validation covers only some requested required aspects
- **THEN** the validation result marks the uncovered requested aspects as missing and does not mark the evidence fully answerable

#### Scenario: Low-confidence validation rejected
- **WHEN** validation confidence is below the configured evidence validation threshold
- **THEN** the evidence is treated as not answerable for the requested aspects

#### Scenario: Safety-sensitive validation uses higher threshold
- **WHEN** the requested aspect is safety-sensitive, including pet toxicity or human edibility
- **THEN** validation requires direct evidence and the configured safety-sensitive threshold before marking the aspect covered

### Requirement: Targeted missing-aspect web fallback
Trusted web fallback for assistant plant-care answers SHALL run only after local evidence validation fails to cover all requested required aspects. Web search SHALL target the missing aspects only, using confirmed taxonomy as the plant term and excluding nicknames, display names, and classifier plant references from search construction.

#### Scenario: RAG covers no requested aspects
- **WHEN** local RAG validation covers none of the requested required aspects
- **THEN** trusted web fallback searches for all requested required aspects using confirmed taxonomy

#### Scenario: RAG covers some requested aspects
- **WHEN** local RAG validation covers some requested required aspects and leaves others missing
- **THEN** trusted web fallback searches only for the missing required aspects using confirmed taxonomy

#### Scenario: Search query excludes display name
- **WHEN** the display plant name differs from confirmed taxonomy
- **THEN** trusted web fallback query construction uses `plant_binomial_name` or `plant_scientific_name` and does not use the display name, nickname, apodo, or classifier plant reference

#### Scenario: Web fallback skipped when local evidence complete
- **WHEN** local evidence validation covers all requested required aspects above threshold
- **THEN** trusted web fallback is not called for that answer

### Requirement: Validated web evidence persistence metadata
The system SHALL persist assistant web fallback evidence only when that web evidence has been validated as relevant to at least one requested required aspect. Persisted validated web evidence SHALL include filterable metadata for confirmed taxonomy, topic, required aspects, covered aspects, language, evidence type, validation confidence, source domain when available, review status, and source provenance.

#### Scenario: Validated web evidence is persisted with covered aspects
- **WHEN** trusted web evidence validates above threshold for one or more requested required aspects
- **THEN** the system persists, chunks, embeds, and indexes only the validated relevant evidence
- **AND** persisted metadata includes `covered_aspects`, `required_aspects`, `topic`, `language`, `evidence_type: "validated_web"`, validation confidence, source domain when available, and `review_status: "auto_ingested"`

#### Scenario: Unvalidated web evidence is not persisted
- **WHEN** web evidence is selected by search but fails aspect validation or falls below the validation threshold
- **THEN** the system does not persist, chunk, embed, or index that evidence

#### Scenario: Multi-source web validation persists only relevant evidence
- **WHEN** web fallback returns multiple candidate sources and only some validate against requested aspects
- **THEN** the system persists only the validated relevant sources and excludes unvalidated or off-aspect sources from embeddings

#### Scenario: Validated web evidence remains filterable
- **WHEN** validated web evidence is persisted
- **THEN** future retrieval can filter or constrain results by confirmed taxonomy, topic, covered aspects, review status, evidence type, and source domain when available
