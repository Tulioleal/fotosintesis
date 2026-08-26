## ADDED Requirements

### Requirement: Source-scoped semantic support binding

Confirmed-plant enrichment SHALL treat schema-valid final semantic judging as the authority for requested-aspect coverage while deterministically binding each accepted support item to supplied trusted source evidence. Binding MUST validate canonical requested aspects, non-empty claim and evidence quote, supplied canonical source identity, source validation status, and applicable safety confidence. Exact substring, keyword, regex, translated-term, token-presence, or language-specific matching MUST NOT determine semantic coverage or persistence eligibility.

#### Scenario: Semantically supported paraphrased quote
- **WHEN** final semantic judging returns coherent source support for a requested aspect and supplied canonical source
- **AND** the evidence quote is a faithful paraphrase or normalization that is not an exact substring of the source package text
- **THEN** lexical mismatch does not remove the supported aspect
- **AND** the support remains eligible for persistence when all structural, trust, and safety requirements pass

#### Scenario: Support references an unknown source
- **WHEN** final semantic judging returns support whose canonical source identity is absent from the supplied evidence package
- **THEN** the support is excluded from accepted enrichment evidence
- **AND** no document, aspect association, chunk, embedding, or vector node is created from that support

#### Scenario: Support cites more than one raw source URL
- **WHEN** a support item's raw `source_urls` list does not contain exactly one non-empty string
- **THEN** the support is excluded from accepted enrichment evidence regardless of how many distinct URLs it references
- **AND** deduplication is never used as the cardinality authority

#### Scenario: Safety support lacks required confidence
- **WHEN** source-bound support targets a registry-marked safety aspect but lacks direct support or the configured safety confidence
- **THEN** the aspect remains missing
- **AND** the support is not persisted for that aspect

### Requirement: Authoritative retrieval metadata convergence

When accepted enrichment content gains new canonical aspect support, the system SHALL converge relational aspect associations and vector retrieval metadata to the complete accepted aspect set while reusing stable content, chunk, embedding, and vector-node identities.

#### Scenario: Existing content gains an aspect
- **WHEN** unchanged accepted content is later validated for a canonical aspect not present in its existing associations
- **THEN** the system idempotently adds the relational aspect association
- **AND** reloads authoritative accepted aspect metadata before vector upsert
- **AND** aspect-filtered retrieval can find the existing content for the newly accepted aspect

#### Scenario: Retry occurs after relational aspect commit
- **WHEN** a new aspect association commits and vector metadata refresh fails transiently
- **THEN** a retry reuses the document, chunks, embeddings, aspect associations, and vector node IDs
- **AND** converges vector metadata without duplicate domain effects

#### Scenario: Concurrent validations add different aspects
- **WHEN** concurrent validation runs accept different aspects for the same unchanged content
- **THEN** relational uniqueness preserves one association per content and aspect
- **AND** the converged vector metadata contains the union of accepted canonical aspects

### Requirement: Caller-scoped evidence eligibility

Trust eligibility for supplied evidence packages SHALL be closed and caller-specific. Production enrichment and normal assistant RAG SHALL construct evidence eligible only for `trusted`. Only the assistant trusted-first fallback path MAY construct evidence eligible for both `trusted` and `external_fallback`, and `external_fallback` SHALL never be treated as globally trusted.

#### Scenario: Production enrichment rejects external fallback
- **WHEN** production enrichment receives an `external_fallback` evidence package
- **THEN** the binding layer rejects support bound to that package
- **AND** no aspect from that package is persisted

#### Scenario: Normal RAG rejects external fallback
- **WHEN** normal assistant RAG evidence contains an `external_fallback` package
- **THEN** support bound to that package is removed

#### Scenario: Trusted-first fallback accepts explicitly permitted external fallback
- **WHEN** the assistant trusted-first fallback path constructs evidence eligible for `trusted` and `external_fallback`
- **THEN** support bound to an explicitly permitted `external_fallback` package remains accepted
- **AND** paraphrased support remains accepted without exact substring matching

### Requirement: Production enrichment efficacy verification

The system SHALL provide deterministic production-path verification and bounded telemetry that measure whether confirmed-plant enrichment increases accepted canonical aspect coverage and makes accepted evidence retrievable. Verification MUST exercise real orchestration, durable handling, PostgreSQL persistence, and pgvector indexing while replacing external provider calls with deterministic provider-boundary fixtures. Telemetry MUST NOT expose taxonomy text, source URLs or domains, claims, quotes, source bodies, prompts, payloads, or idempotency keys.

#### Scenario: Empty confirmed species gains retrievable support
- **WHEN** a validated confirmed species has no local evidence and deterministic trusted acquisition returns final-judge-supported evidence
- **THEN** the real durable handler persists validation, content, aspect support, chunks, embeddings, and vector nodes
- **AND** terminal bounded metadata reflects final coverage
- **AND** later production aspect-filtered retrieval returns the accepted evidence with provenance

#### Scenario: Local evidence is complete
- **WHEN** production local semantic judging covers every policy-required aspect
- **THEN** external search and page fetching are not called
- **AND** acquisition avoidance and zero coverage gain are recorded with bounded metadata

#### Scenario: Acquired evidence is unusable
- **WHEN** deterministic acquisition returns untrusted, unsupported, contradictory, or safety-inadequate evidence
- **THEN** the production path creates no knowledge or vector effects from that evidence
- **AND** records a bounded partial or failed lifecycle outcome according to final accepted coverage

#### Scenario: Efficacy metrics are emitted
- **WHEN** an enrichment run reaches a terminal outcome
- **THEN** bounded telemetry records policy version, acquisition avoidance, local covered count, final covered count, coverage gain, accepted aspect count, search count, lifecycle outcome, and completion duration
- **AND** metric labels contain no evidence or plant-specific content

#### Scenario: Deterministic efficacy corpus is evaluated
- **WHEN** the enrichment efficacy suite runs
- **THEN** it covers empty, sparse, complete, contradictory, multilingual, safety-sensitive, retry, policy-change, and source-change cases
- **AND** reports unsupported persistence, duplicate effects, and later aspect-filtered retrieval success
