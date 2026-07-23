## Context

Candidate confirmation currently validates ownership and taxonomy, marks the candidate confirmed, and commits immediately. It does not coordinate follow-up knowledge work. The archived `add-durable-background-jobs` change provides PostgreSQL-backed scheduling, leasing, retries, typed handlers, idempotency, metadata-only status, and an independent worker. This change adds a confirmation-driven enrichment workload on that foundation.

The knowledge stack already provides canonical `RequiredAspect` identifiers, LlamaIndex pgvector retrieval, trusted-source search and safe page fetching, semantic answerability judging, final combined judging, validated claim construction, and convergent embedding/indexing. Those components are currently organized around assistant chat state. Profile construction persists a snapshot and does not automatically refresh sections after later evidence ingestion.

Botanical coverage remains multilingual and semantic. Hardcoded keyword matching, token checks, regex routing, translated word lists, and language-specific heuristics are not valid coverage or acceptance mechanisms.

## Goals / Non-Goals

**Goals:**

- Durably schedule enrichment in the same successful workflow boundary as validated candidate confirmation.
- Use accepted GBIF key plus normalized binomial as canonical identity when both are available.
- Evaluate local evidence against an explicit initial set of canonical profile aspects.
- Search only locally missing aspects while calculating final status against the complete policy.
- Reuse trusted-source, answerability, provenance, embedding, and indexing rules without weakening safety thresholds.
- Make active work and persisted evidence idempotent at their separate identity layers.
- Expose bounded enrichment lifecycle while profile navigation remains available.
- Make accepted evidence retrievable by later assistant requests.

**Non-Goals:**

- No enrichment for unconfirmed candidates, every visual candidate, or unvalidated free-form names.
- No arbitrary crawler, new trust policy, deterministic semantic heuristic, or assistant fallback redesign.
- No section-level profile regeneration or replacement policy.
- No evidence freshness, maximum-age, supersession, or historical-candidate backfill framework.
- No new queue or worker infrastructure beyond `durable-background-jobs`.

## Decisions

### Decision 1: Confirm, schedule, and associate atomically

Move confirmation orchestration above the repository commit boundary. The confirmation update, system-owned `enrich_confirmed_plant` enqueue, and owner/candidate association use one request-owned SQLAlchemy session and commit once. If durable scheduling is disabled or enqueueing fails, confirmation returns temporary unavailability and rolls back. Worker execution may be disabled independently while committed jobs remain pending.

Associations are unique by candidate and enrichment policy version, not candidate alone. Replaying confirmation under the same policy returns that association. If the current policy is newer than the candidate's existing associations, confirmation creates or joins work for the current policy and stores a new association. This preserves request replay while allowing policy-version enrichment.

Shared system jobs allow concurrent users confirming the same canonical species and policy to collapse active work without assigning the shared job to one user. Candidate ownership remains the authorization boundary for status.

Alternative considered: publish after confirmation commits or skip scheduling when disabled. Rejected because either creates a confirmed candidate without the required durable workflow. Per-user jobs are rejected because they defeat species-level active deduplication.

### Decision 2: Use the proposal's composite taxonomy identity

Canonical species identity contains accepted GBIF key plus normalized binomial when both are available. A taxonomy-validated normalized binomial is the fallback when GBIF supplies no accepted key. Display names, nicknames, and unvalidated free-form names never enter identity.

The normalized key representation distinguishes `(accepted_gbif_key, normalized_binomial)` pairs. A changed accepted key or normalized binomial can therefore create a new identity as required by the source proposal. The payload and persisted provenance retain both fields.

Taxonomy validation is itself source-backed. A changed GBIF resolution creates a new taxonomy provenance snapshot or `taxonomy_source_version`, linked to the prior snapshot when known, without rewriting prior evidence provenance. This taxonomy version is separate from evidence-page `source_version`.

Alternative considered: GBIF-only equivalence when a key exists. Rejected because the immutable proposal explicitly requires jobs and deduplication keys to include both values when both are available.

### Decision 3: Make enrichment policy version 1 explicit

Policy version 1 requires these canonical aspects:

| Group | Required aspects |
| --- | --- |
| General | `general_care_summary` |
| Conditions | `light_exposure`, `soil_drainage`, `climate_temperature_range`, `humidity_preference` |
| Routine care | `watering_frequency_or_trigger`, `watering_amount`, `nutrition_feeding_schedule`, `nutrition_fertilizer_type` |
| Pests | `pest_identification`, `pest_prevention_steps` |
| Diseases | `disease_identification`, `disease_prevention_steps` |
| Safety | `toxicity_pet_safety`, `toxicity_human_edibility`, `toxicity_child_safety`, `toxicity_handling_precautions` |

Every identifier must exist in `REQUIRED_ASPECT_METADATA`. Safety classification and stricter thresholds come from the registry rather than a duplicate policy list. Acquisition groups contain at most four aspects, use at most five provider searches per run, and group registry domains together where possible. The enrichment job permits at most three durable attempts.

Changing required aspects, search bounds, or acceptance semantics increments the policy version. Evidence identity remains independent from policy version.

Alternative considered: defer the aspect set to implementation constants or require the entire registry. Rejected because the former leaves `complete` undefined and the latter makes cost and useful completion unbounded.

### Decision 4: Use explicit aspect sets through the workflow

The handler maintains four distinct sets:

- `required_aspects`: every aspect in the declared policy.
- `local_covered_aspects`: aspects accepted by local semantic judging.
- `acquisition_aspects`: `required_aspects - local_covered_aspects`.
- `final_covered_aspects`: aspects accepted by final evidence determination, using the normalized all-required local result when acquisition is unnecessary or final combined judging when acquisition runs.

Local retrieval and semantic judging evaluate all `required_aspects`. External query construction receives only `acquisition_aspects`. When `acquisition_aspects` is empty, the normalized all-required local result establishes `final_covered_aspects` without another provider call. When acquisition runs, the final combined judge receives all `required_aspects`, local evidence and its normalized result, and selected acquired evidence; it may confirm or revise local coverage. Final missing aspects are always `required_aspects - final_covered_aspects`, and public completion is always calculated against the complete required set.

Alternative considered: judge only acquisition aspects and union them mechanically with local coverage. Rejected because it bypasses the existing combined answerability judge's authority over the complete evidence package.

### Decision 5: Acquire only missing aspects through existing trust gates

When the normalized all-required local result is full, it establishes final coverage, the handler records avoided acquisition, and the job completes without external calls. Otherwise, the handler builds bounded trusted-source searches from composite taxonomy identity and only `acquisition_aspects`, using registry query guidance and existing URL/domain and page-fetch safety gates.

Only normalized `full` or useful `partial` final source support is eligible for persistence. Contradictory, insufficient, off-aspect, unsupported, or untrusted acquired evidence is not persisted. Safety-sensitive aspects retain direct-evidence and strict-threshold requirements.

Alternative considered: call `KnowledgeAcquisitionService.retrieve_or_acquire` unchanged. Rejected because its current acquisition trigger is chunk-count based and can precede semantic aspect acceptance. Lower-level retrieval, search, fetch, judge, and ingestion components are reused behind the semantic gate.

### Decision 6: Separate content, aspect support, validation, and result records

Persist small contextualized source-supported claims instead of complete fetched pages or generated profile prose. Metadata ownership is explicit:

| Record | Owned metadata |
| --- | --- |
| Content document | Composite species identity, canonical source URL/domain, source version, normalized content hash, immutable claim/quote content, required `source_retrieved_at`, nullable `source_published_at`, enrichment provenance |
| Aspect-support association | One document, one supported canonical aspect, support confidence and review status |
| Validation run | Policy version, required/covered/missing sets, answerability status, judge confidence and validation metadata |
| Job result | Bounded aggregate covered/missing identifiers, counts, limitations, and lifecycle outcome |

The content identity hashes composite species identity, canonical source, source version, and normalized persisted-content hash. Aspect support is unique by content document and individual aspect. Policy version and complete aspect sets belong to validation runs and never participate in document, chunk, embedding, vector-node, or aspect-association uniqueness. One multi-aspect document is embedded once.

For source pages, normalized ETag, Last-Modified, or provider version becomes `source_version`; otherwise normalized accepted content supplies a stable version. `source_version` is provenance and identity metadata, not a new evidence-eligibility rule. Changed source version or content hash may create a new content record while preserving the older audit record.

Alternative considered: store required and covered sets directly as mutable document identity metadata. Rejected because policy changes would require mutating immutable evidence or duplicating unchanged content.

### Decision 7: Separate active sharing, run replay, and terminal outcomes

An active deduplication key hashes composite species identity and policy version and is unique only for `pending` or `processing` jobs. Each logical run also has a permanent idempotency key so request and worker replay converge. Terminal `complete`, `partial`, or `failed` jobs leave active uniqueness atomically, allowing a later eligible confirmation to create a new run.

The handler maps internal outcomes to public lifecycle explicitly:

| Internal outcome | Public behavior |
| --- | --- |
| All required aspects covered | `complete` |
| At least one required aspect covered and others missing | `partial` |
| Search/judging succeeds but no evidence is accepted | `failed` with `insufficient_evidence` |
| Retryable provider, judge, database, or indexing error | Retry, then `failed` after attempt exhaustion |
| Invalid payload, unsupported version, or permanent invariant error | `failed` without retry |

`insufficient` remains an internal answerability/acquisition result, never a sixth public job state. `JobError` is sanitized failure metadata separate from complete or partial result payloads.

Alternative considered: use permanent `(job_type, idempotency_key)` uniqueness as the species-level lock. Rejected because terminal jobs would block future runs.

### Decision 8: Expose owner-authorized status without regenerating profiles

Confirmation and profile contracts expose metadata-only enrichment references: job ID, lifecycle, and bounded covered/missing outcomes. The chosen implementation uses a candidate-scoped status read backed by the candidate-policy association. Unknown and foreign candidates have identical not-found behavior, and raw payload/evidence content is never returned.

The profile endpoint always returns the latest persisted profile snapshot, its snapshot sources and limitations, and applicable enrichment metadata. Pending, processing, partial, or failed enrichment never blocks navigation. Terminal query invalidation refreshes status and snapshot metadata but does not imply that newly indexed evidence was incorporated into persisted sections. New evidence is immediately available to assistant retrieval and future profile generation or refresh behavior.

Alternative considered: block navigation or regenerate sections automatically. Both are rejected because provider latency is unbounded and section regeneration is explicitly outside scope.

### Decision 9: Reuse durable-job safeguards and add only required metrics

Add enrichment metrics for avoided acquisition, completion time, and partial outcomes. Existing durable-job telemetry continues to report retries and failures. Existing metadata-only status, bounded labels, and sensitive-payload logging restrictions remain implementation safeguards rather than new product metrics requirements.

## Risks / Trade-offs

- **Composite identity fragments after a normalized-binomial change** -> Follow the proposal literally and preserve linked taxonomy provenance for later reconciliation.
- **Provider cost grows with policy breadth** -> Use the explicit bounded aspect set, missing-only acquisition, at most four aspects per group, and at most five searches.
- **Concurrent confirmations race** -> Use active-scope uniqueness, permanent run idempotency, and policy-versioned candidate associations.
- **Weak evidence pollutes retrieval** -> Preserve trusted-source validation, combined semantic judging, safety thresholds, and source-support-only persistence.
- **Crash occurs after evidence commit** -> Stable content, aspect-association, chunk, and vector identities make retries converge.
- **Existing profile sections remain stale** -> Describe them as the latest persisted snapshot and leave regeneration to a separate change.

## Migration Plan

1. Add active-work identity, policy-versioned candidate associations, content/aspect/validation metadata, and the closed job type through additive models and migrations.
2. Deploy the policy, reusable semantic coverage service, compatible handler, and worker before changing confirmation behavior.
3. Deploy transactional confirmation enqueueing, candidate-authorized status, generated contracts, and profile polling. If enqueueing is unavailable, confirmation remains temporarily unavailable rather than committing without a job.
4. Verify empty, covered, partial, insufficient, failed, terminal-new-run, policy-upgrade, retry, duplicate, restart, authorization, and multilingual semantic cases.

Rollback disables worker consumption while preserving compatible durable enqueueing, or makes confirmation temporarily unavailable if compatible enqueueing cannot remain deployed. It never commits confirmation without an enrichment job. Jobs, associations, evidence, and provenance remain additive for forward recovery.

## Open Questions

No blocking product questions remain. Policy version 1, its required aspects, search bounds, and attempt limit are defined above; future semantic-scope changes require a new policy version.
