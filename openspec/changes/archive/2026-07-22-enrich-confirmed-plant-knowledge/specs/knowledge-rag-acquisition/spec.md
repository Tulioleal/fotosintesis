## ADDED Requirements

### Requirement: Offline aspect-targeted evidence acquisition

The knowledge acquisition system SHALL support non-chat-time confirmed-species acquisition with separate complete `required_aspects` and missing-only `acquisition_aspects`. Search SHALL target only `acquisition_aspects`. When acquisition runs, final combined semantic judging SHALL evaluate all `required_aspects` using local and selected acquired evidence; when acquisition is unnecessary, the normalized all-required local result SHALL establish final coverage without invoking acquisition.

#### Scenario: Offline enrichment requests missing aspects
- **WHEN** enrichment supplies composite taxonomy, `required_aspects`, and `acquisition_aspects`
- **THEN** acquisition searches only `acquisition_aspects` using confirmed taxonomy
- **AND** excludes display names, nicknames, classifier references, and unvalidated free-form names

#### Scenario: Final combined evidence is judged
- **WHEN** trusted acquired evidence is available
- **THEN** the combined judge receives every `required_aspect`, local evidence and its normalized result, selected acquired evidence, and source metadata
- **AND** returns normalized final covered and missing aspects, source support, contradictions, reason, and confidence

#### Scenario: Semantic evidence uses multilingual phrasing
- **WHEN** evidence directly supports a required aspect using non-English, synonymous, or paraphrased wording
- **THEN** semantic judging can accept it without hardcoded keyword, translated-term, regex, substring, or token-presence gates

#### Scenario: Acquisition adds no answerable support
- **WHEN** trusted search and safe page fetching produce no accepted support for `acquisition_aspects`
- **THEN** acquisition returns internal `insufficient`
- **AND** does not create an unsupported knowledge document

### Requirement: Explicit enrichment evidence metadata ownership

The system SHALL persist accepted enrichment evidence through separate immutable content, individual aspect-support, validation-run, and bounded job-result records. Required, covered, and missing aspect sets SHALL belong to validation runs rather than content-document identity.

#### Scenario: Accepted content document is persisted
- **WHEN** final judging returns source support for a claim
- **THEN** the content document stores composite species identity, canonical source and domain, source version, content hash, immutable claim/quote content, required `source_retrieved_at`, nullable `source_published_at`, and enrichment provenance

#### Scenario: Individual aspect support is persisted
- **WHEN** a content document supports one or more canonical aspects
- **THEN** each supported aspect has an idempotent association containing support confidence and review status

#### Scenario: Validation run is persisted
- **WHEN** semantic validation completes with accepted support
- **THEN** the validation record stores policy version, required aspects, covered aspects, missing aspects, answerability status, judge confidence, and validation metadata

#### Scenario: Bounded job result is persisted
- **WHEN** enrichment reaches `complete` or useful `partial`
- **THEN** the job result stores bounded aggregate covered and missing identifiers, counts, limitations, and lifecycle outcome
- **AND** does not duplicate immutable content or validation metadata

#### Scenario: Source publication date is unknown
- **WHEN** accepted evidence has no reliable publication date
- **THEN** `source_published_at` is null
- **AND** `source_retrieved_at` remains required

#### Scenario: Unsupported acquired content is excluded
- **WHEN** acquired content is absent from normalized final source support or final judging is `insufficient` or `contradictory`
- **THEN** the system does not persist, chunk, embed, or index that content

#### Scenario: Full fetched page is available
- **WHEN** trusted page fetching returns a complete source body
- **THEN** the system persists small contextualized source-supported claims rather than the full page by default

### Requirement: Enrichment evidence convergence and retrieval

Content documents SHALL converge by composite species identity, canonical source, source version, and content hash. Individual aspect support SHALL converge by content and canonical aspect. Source version SHALL be provenance and content-identity metadata, not an evidence-eligibility rule. Accepted content SHALL be embedded and indexed once through the existing vector path and SHALL be retrievable by later assistant requests.

#### Scenario: Equivalent evidence is ingested repeatedly
- **WHEN** retries submit the same content and aspect support
- **THEN** the system reuses the document, aspect associations, chunks, embeddings, and vector nodes

#### Scenario: Policy version changes
- **WHEN** unchanged content and aspect support are accepted under a later policy
- **THEN** later validation provenance is retained
- **AND** content, aspect associations, chunks, embeddings, and vector nodes are not duplicated

#### Scenario: Accepted evidence becomes retrievable
- **WHEN** relational persistence and vector indexing complete
- **THEN** later assistant retrieval for the same composite species and covered aspect can find the evidence with source, date, confidence, review, and validation provenance

#### Scenario: Vector indexing fails after relational persistence
- **WHEN** accepted evidence commits but indexing fails transiently
- **THEN** retry converges through stable identities without duplicating relational evidence

#### Scenario: Updated source is ingested
- **WHEN** source version or accepted content hash changes
- **THEN** the system may create a new content version
- **AND** preserves prior source and validation records
