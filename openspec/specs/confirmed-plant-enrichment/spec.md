## Purpose

Define the durable enrichment lifecycle triggered by taxonomically validated candidate confirmation: composite canonical species identity, semantic evidence coverage against enrichment policy version 1, targeted missing-aspect acquisition, idempotent evidence persistence, and owner-authorized bounded status.

## Requirements

### Requirement: Composite canonical species identity

The system SHALL identify confirmed-plant enrichment by accepted GBIF key plus normalized binomial when both are supplied by taxonomy validation. When no accepted GBIF key is available, the system SHALL use the taxonomy-validated normalized binomial as fallback. Display names, nicknames, and unvalidated free-form names MUST NOT become enrichment identity.

#### Scenario: Accepted GBIF key and binomial are available
- **WHEN** a confirmed validated candidate has an accepted GBIF key and normalized binomial
- **THEN** job, active-deduplication, and evidence identities include both values
- **AND** payload and provenance retain both values

#### Scenario: Validated taxonomy has no accepted GBIF key
- **WHEN** a confirmed validated candidate has no accepted GBIF key but has a normalized binomial from validation
- **THEN** the normalized binomial is the canonical fallback identity
- **AND** no display or free-form name substitutes for it

#### Scenario: No validated canonical identity exists
- **WHEN** validation supplies neither an accepted GBIF key nor a normalized binomial
- **THEN** the system does not schedule enrichment

#### Scenario: Taxonomy resolution changes
- **WHEN** a later validated taxonomy snapshot changes the accepted GBIF key or normalized binomial
- **THEN** the changed composite values may create a new canonical identity and taxonomy source version
- **AND** prior taxonomy and evidence provenance remain preserved

### Requirement: Enrichment policy version 1

Enrichment policy version 1 SHALL require `general_care_summary`, `light_exposure`, `soil_drainage`, `climate_temperature_range`, `humidity_preference`, `watering_frequency_or_trigger`, `watering_amount`, `nutrition_feeding_schedule`, `nutrition_fertilizer_type`, `pest_identification`, `pest_prevention_steps`, `disease_identification`, `disease_prevention_steps`, `toxicity_pet_safety`, `toxicity_human_edibility`, `toxicity_child_safety`, and `toxicity_handling_precautions`. Every identifier SHALL exist in the canonical aspect registry, and safety classification SHALL come from that registry.

#### Scenario: Policy version 1 is resolved
- **WHEN** the handler loads enrichment policy version 1
- **THEN** its complete required-aspect set is exactly the listed canonical aspects
- **AND** registry-marked safety aspects retain the existing stricter thresholds

#### Scenario: Acquisition is grouped
- **WHEN** policy version 1 has multiple missing aspects
- **THEN** each acquisition group contains at most four aspects
- **AND** one run performs at most five provider searches
- **AND** registry domains are grouped together where possible

#### Scenario: Durable attempts are exhausted
- **WHEN** a policy version 1 job reaches three attempts without a terminal useful outcome
- **THEN** the durable job reaches `failed` according to the common retry rules

#### Scenario: Policy semantics change
- **WHEN** required aspects, search bounds, or acceptance semantics change
- **THEN** the enrichment policy version changes

### Requirement: Explicit coverage and acquisition aspect sets

The enrichment workflow SHALL distinguish the complete `required_aspects`, semantically accepted `local_covered_aspects`, missing-only `acquisition_aspects`, and final semantically accepted `final_covered_aspects`. External acquisition SHALL receive only `acquisition_aspects`. Final evidence determination and terminal status SHALL always evaluate the complete `required_aspects` set, using the normalized local result directly when acquisition is unnecessary and combined judging when acquisition runs.

#### Scenario: Local evidence covers every required aspect
- **WHEN** local semantic judging covers all `required_aspects`
- **THEN** `acquisition_aspects` is empty
- **AND** `final_covered_aspects` is established from the normalized all-required local result
- **AND** the handler completes without external search, page fetch, or structured provider acquisition
- **AND** records an avoided-acquisition outcome

#### Scenario: Local evidence covers a subset
- **WHEN** local semantic judging accepts only a subset of `required_aspects`
- **THEN** `local_covered_aspects` contains that subset
- **AND** `acquisition_aspects` equals `required_aspects` minus `local_covered_aspects`

#### Scenario: Combined evidence is judged
- **WHEN** trusted acquisition runs for `acquisition_aspects`
- **THEN** final combined judging receives all `required_aspects`, available local evidence and its normalized result, and selected acquired evidence
- **AND** final missing aspects equal `required_aspects` minus `final_covered_aspects`

#### Scenario: Deterministic text check disagrees with semantic judging
- **WHEN** semantic judging validates coherent source support despite language, synonym, spelling, or phrasing differences
- **THEN** keyword, regex, substring, translated-term, or token-presence mismatch does not change aspect coverage

### Requirement: Missing-aspect trusted acquisition

The enrichment handler SHALL acquire evidence only for `acquisition_aspects` using confirmed composite taxonomy, existing trusted-source validation, bounded safe page fetching, and combined answerability judging. It MUST NOT persist acquired evidence that is untrusted, off-aspect, insufficient, contradictory, or absent from normalized final source support.

#### Scenario: Missing aspects are searched
- **WHEN** `acquisition_aspects` is non-empty
- **THEN** external query construction uses confirmed taxonomy and only those aspects
- **AND** it does not search locally covered aspects

#### Scenario: Acquired evidence supports a subset
- **WHEN** final combined judging accepts source support for only some `acquisition_aspects`
- **THEN** only those supported claims and individual aspects become eligible for persistence
- **AND** final missing aspects equal `required_aspects` minus `final_covered_aspects`

#### Scenario: Safety evidence is weak
- **WHEN** evidence for a registry-marked safety aspect lacks direct support or the strict threshold
- **THEN** the aspect remains missing
- **AND** that evidence is not persisted as support for the aspect

#### Scenario: Acquired evidence is unusable
- **WHEN** final judging returns `insufficient` or `contradictory`, or evidence fails source trust validation
- **THEN** the system does not persist, chunk, embed, or index that acquired evidence

### Requirement: Durable enrichment lifecycle outcomes

Confirmed-plant enrichment SHALL use the public `pending`, `processing`, `complete`, `partial`, and `failed` lifecycle. Internal `insufficient` evidence status MUST NOT become a sixth public lifecycle state. Useful partial completion SHALL be distinct from total failure.

#### Scenario: Every required aspect is covered
- **WHEN** `final_covered_aspects` contains every `required_aspect`
- **THEN** the job becomes `complete`

#### Scenario: Useful subset is covered
- **WHEN** at least one required aspect has accepted support and other required aspects remain missing
- **THEN** the job becomes `partial`
- **AND** bounded result metadata identifies covered and missing canonical aspects

#### Scenario: Search succeeds without accepted support
- **WHEN** retrieval and acquisition complete without a retryable error but no required aspect has accepted support
- **THEN** the job becomes `failed`
- **AND** failure metadata uses the bounded `insufficient_evidence` category

#### Scenario: Retryable operation fails
- **WHEN** a provider, judge, database, embedding, or indexing operation reports a retryable failure before the attempt limit
- **THEN** the job is retried through the common durable-job policy
- **AND** becomes `failed` if attempts are exhausted without useful accepted support

#### Scenario: Permanent operation fails
- **WHEN** payload validation, payload version, policy version, or a permanent invariant is invalid
- **THEN** the job becomes `failed` without retry
- **AND** exposes only sanitized failure metadata

#### Scenario: Worker restarts during enrichment
- **WHEN** the API or worker terminates after scheduling commit or during a leased attempt
- **THEN** pending or expired-leased enrichment remains recoverable through the durable worker

### Requirement: Active run and policy-version association idempotency

Equivalent active work SHALL collapse by composite canonical species identity and enrichment policy version only while jobs are `pending` or `processing`. Candidate associations SHALL be unique by candidate and policy version. Permanent run idempotency SHALL preserve request and worker replay without making terminal jobs permanent active-work locks.

#### Scenario: Different owners confirm equivalent species concurrently
- **WHEN** equivalent confirmations use the same composite identity and policy while work is `pending` or `processing`
- **THEN** the system reuses one durable enrichment job
- **AND** each owner can observe applicable status without accessing another owner's candidate

#### Scenario: Confirmation is replayed under the same policy
- **WHEN** a candidate already has an association for the current policy version
- **THEN** replay returns that association
- **AND** does not create another run

#### Scenario: Candidate has only an older policy association
- **WHEN** confirmation is processed under a newer policy version and the candidate has no association for that version
- **THEN** the system creates or joins active work for the newer policy
- **AND** persists a separate candidate-policy association

#### Scenario: Previous equivalent work is terminal
- **WHEN** an eligible confirmation has no current-policy association and prior equivalent jobs are `complete`, `partial`, or `failed`
- **THEN** prior terminal jobs do not block a new run

### Requirement: Evidence persistence idempotency

Persisted enrichment content SHALL be unique by composite species identity, canonical source, source version, and content hash. Individual aspect support SHALL be unique by content document and canonical aspect. Policy version and complete required, covered, or missing sets MUST NOT participate in content, chunk, embedding, vector-node, or aspect-support uniqueness.

#### Scenario: Handler retries after evidence commit
- **WHEN** evidence commits before lease loss or completion recording
- **THEN** the next attempt reuses content, individual aspect support, chunks, embeddings, and vector nodes

#### Scenario: Multi-aspect content is accepted
- **WHEN** one content document supports multiple canonical aspects
- **THEN** it has one idempotent association per supported aspect
- **AND** is chunked, embedded, and indexed once

#### Scenario: Later policy accepts unchanged evidence
- **WHEN** a later validation policy accepts the same content and individual aspect support
- **THEN** the validation run records the later policy
- **AND** content, aspect support, chunks, embeddings, and vector nodes are not duplicated

#### Scenario: Source content changes
- **WHEN** source version or accepted content hash changes
- **THEN** the system may create a new content version
- **AND** retains the older audit record

### Requirement: Owner-authorized bounded status

Each confirming owner SHALL be able to observe applicable enrichment lifecycle and bounded result metadata without gaining access to another owner's candidate or raw job/evidence content.

#### Scenario: Owner reads applicable status
- **WHEN** an authenticated owner requests status for their confirmed candidate and policy association
- **THEN** the system returns lifecycle, timestamps, bounded counts, covered aspects, missing aspects, and limitation categories
- **AND** excludes raw payloads, source bodies, claims, quotes, and prompts

#### Scenario: Another owner requests status
- **WHEN** a user requests enrichment status through a candidate they do not own
- **THEN** the system returns the same not-found behavior used for an unknown candidate

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

### Requirement: Accepted durable enrichment progress

The system SHALL checkpoint accepted enrichment progress by job. Useful accepted coverage SHALL be the union of semantically accepted local aspects and durably persisted accepted aspects. Final semantic judge output that has not passed source binding and persistence MUST NOT by itself make a failed or exhausted job `partial`.

#### Scenario: Judge support is rejected before persistence

- **WHEN** final semantic judging reports covered aspects but every support item is rejected before persistence and no accepted local coverage exists
- **THEN** the durable checkpoint has no useful accepted coverage
- **AND** operational exhaustion produces `failed`, not `partial`

#### Scenario: Accepted evidence survives operational failure

- **WHEN** at least one required aspect has accepted local or persisted evidence before a later operational failure exhausts retries
- **THEN** the job becomes `partial`
- **AND** bounded result metadata identifies covered aspects, missing aspects, and the operational limitation

#### Scenario: Accepted evidence is not fully indexed

- **WHEN** accepted evidence persists but its vector indexing does not finish before operational exhaustion
- **THEN** the job becomes `partial` with `indexing_deferred`
- **AND** it is not reported as complete or total failure

### Requirement: Serialized progress convergence

Progress checkpoint aspect sets SHALL only grow across retries and concurrent accepted evidence operations. Read-merge-write mutations and terminal decisions MUST serialize on the progress row, while evidence and its paired checkpoint update SHALL commit in the same relational transaction.

#### Scenario: Concurrent claims accept different aspects

- **WHEN** two concurrent transactions add different accepted aspects to one enrichment checkpoint
- **THEN** the persisted checkpoint contains the union of both aspects
- **AND** neither update erases the other

#### Scenario: Checkpoint update fails

- **WHEN** a paired checkpoint update fails before an evidence transaction commits
- **THEN** the paired evidence transaction rolls back
- **AND** no evidence-only or checkpoint-only milestone remains

### Requirement: Coverage-balanced local retrieval

Local enrichment retrieval SHALL select canonical evidence candidates per requested aspect and balance the bounded result across requested aspects before semantic judging. Metadata filtering SHALL select candidates only; semantic judging SHALL remain authoritative for multilingual botanical coverage.

#### Scenario: Required aspect evidence is below a global top-k

- **WHEN** unrelated higher-scoring chunks would displace a requested aspect from a global top-k result
- **THEN** the aspect-filtered retrieval still supplies that aspect's eligible candidate to semantic judging

#### Scenario: Multiple aspects have candidates

- **WHEN** several requested aspects each have eligible candidates
- **THEN** each available aspect contributes one candidate before any aspect contributes a second
- **AND** stable chunk identities are deduplicated

### Requirement: Fetched-only confirmed enrichment evidence

Confirmed-plant enrichment SHALL send only successfully fetched trusted page content to final acquired-evidence judging and persistence. Search snippets MAY remain available to the separate degraded assistant fallback but MUST NOT create confirmed-plant documents, chunks, embeddings, aspect support, or vector nodes.

#### Scenario: Fetch fails but a search snippet exists

- **WHEN** a trusted search result has a snippet but page fetching fails, is unsafe, exceeds bounds, or returns an unsupported content type
- **THEN** the snippet does not contribute acquired enrichment coverage
- **AND** it produces no confirmed-plant persistence or vector effects

#### Scenario: Mixed fetched and snippet-only results

- **WHEN** a bounded acquisition contains successful fetched pages and snippet-only failures
- **THEN** only fetched trusted content enters final enrichment judging and persistence eligibility

### Requirement: Reconfirmation preserves explicit run semantics

Same-candidate same-policy confirmation replay SHALL return its existing association whether the associated job is active or terminal. A newer policy SHALL use a separate association. Switching to a sibling candidate MUST NOT cancel already committed species-level work.

#### Scenario: Same candidate is reconfirmed after terminal status

- **WHEN** a candidate already has a current-policy association whose job is complete, partial, or failed
- **THEN** confirmation replay returns that association
- **AND** does not silently create a rerun

#### Scenario: Candidate is confirmed under a newer policy

- **WHEN** the candidate has only an older-policy association
- **THEN** confirmation creates or joins work for the newer policy
- **AND** preserves the older association and evidence history

### Requirement: Canonical later assistant retrieval

Accepted and indexed enrichment evidence SHALL be retrievable by later assistant requests using canonical identity resolved server-side from the current user's confirmed, taxonomically validated candidate. Client taxonomy strings or canonical keys MUST NOT override that identity.

#### Scenario: Assistant opens from a confirmed profile

- **WHEN** the profile assistant link carries the confirmed candidate ID
- **THEN** the backend resolves accepted GBIF key and normalized binomial from the owned confirmed candidate
- **AND** aspect-filtered retrieval uses that canonical identity

#### Scenario: Garden display matching selects another plant

- **WHEN** a client display hint could match a different garden plant after candidate identity was resolved
- **THEN** candidate-resolved canonical identity remains authoritative
- **AND** retrieval does not combine taxonomy from different species

### Requirement: Proposal 11 remains independent

Confirmed-plant enrichment MUST NOT regenerate, invalidate, replace, version, or refresh existing persisted profile sections and MUST NOT schedule profile-refresh work.

#### Scenario: Enrichment completes for an existing profile

- **WHEN** accepted evidence is persisted and indexed after a profile snapshot already exists
- **THEN** later assistant retrieval can use the evidence
- **AND** the existing profile sections, sources, confidence, and limitations remain unchanged
- **AND** no profile-refresh job is created
