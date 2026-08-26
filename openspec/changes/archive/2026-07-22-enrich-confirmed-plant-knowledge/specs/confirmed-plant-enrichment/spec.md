## ADDED Requirements

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
