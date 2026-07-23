## 1. Identity, Policy, and Contracts

- [x] 1.1 Add a canonical species value object whose key includes accepted GBIF key plus normalized binomial when both are available and uses taxonomy-validated normalized binomial as fallback.
- [x] 1.2 Add taxonomy identity tests for both-value keys, binomial fallback, changed accepted key, changed normalized binomial, and rejection of display or unvalidated free-form names.
- [x] 1.3 Define enrichment policy version 1 with the exact required aspects listed in the spec, registry-owned safety classification, at most four aspects per search group, at most five searches, and at most three durable attempts.
- [x] 1.4 Add policy contract tests proving the complete version 1 aspect set, bounds, registry membership, and policy-version change requirement.
- [x] 1.5 Define versioned payloads carrying composite taxonomy and policy version plus bounded complete/partial results, separate sanitized failed-job error metadata including `insufficient_evidence`, and authorized status metadata.
- [x] 1.6 Define typed workflow fields for `required_aspects`, `local_covered_aspects`, `acquisition_aspects`, `final_covered_aspects`, and final missing aspects.
- [x] 1.7 Add an active-work key builder from composite species identity and policy version, and a separate permanent run idempotency key for request/worker replay.

## 2. Persistence and Migration

- [x] 2.1 Extend application jobs with optional active deduplication identity and PostgreSQL uniqueness only for matching `pending` or `processing` jobs while preserving permanent per-run `(job_type, idempotency_key)` replay safety.
- [x] 2.2 Add owner/candidate-to-enrichment-job associations unique by candidate and policy version, with indexes for current-policy status lookup and preserved older associations.
- [x] 2.3 Add immutable content identity fields for composite species, canonical source, source version, normalized content hash, required retrieval time, nullable publication time, and enrichment provenance.
- [x] 2.4 Add idempotent document-to-individual-aspect support storage with support confidence and review status.
- [x] 2.5 Add validation-run storage for policy version, required/covered/missing sets, answerability status, judge confidence, and validation metadata without making those fields content identity.
- [x] 2.6 Add taxonomy provenance snapshots or taxonomy source versions for changed GBIF resolutions without conflating them with evidence-page source versions.
- [x] 2.7 Add an Alembic migration for active uniqueness, policy-versioned associations, content/aspect/validation metadata, taxonomy provenance, indexes, constraints, and the closed `enrich_confirmed_plant` job type while preserving existing rows.
- [x] 2.8 Add repository operations that atomically create or reuse active work, resolve same-candidate same-policy replay, preserve older policy associations, release active uniqueness through terminal transitions, and authorize candidate-owned status.

## 3. Reusable Semantic Coverage

- [x] 3.1 Extract answerability normalization, canonical aspect constraints, contradiction handling, source-support validation, and safety threshold selection into a public service reusable by assistant chat and offline enrichment.
- [x] 3.2 Add local retrieval and semantic judging for the complete policy `required_aspects`, returning normalized `local_covered_aspects` and initial missing aspects.
- [x] 3.3 Derive `acquisition_aspects` exactly as `required_aspects - local_covered_aspects` without keyword, regex, translated-term, substring, or token-presence rules.
- [x] 3.4 When acquisition is unnecessary, establish final coverage from the normalized all-required local result; when acquisition runs, make final combined judging receive all `required_aspects`, local evidence and its normalized result, and selected acquired evidence.
- [x] 3.5 Preserve direct-evidence and stricter threshold handling for registry-marked safety aspects and conservative typed degradation for malformed judge output.
- [x] 3.6 Update the assistant path to use the extracted service without changing chat-time retrieval, fallback, or persistence behavior.
- [x] 3.7 Add semantic coverage tests for full local coverage, partial local coverage, acquired completion, revised local coverage, insufficient, contradictory, safety-sensitive, malformed-output, non-English, synonym, and paraphrase cases.

## 4. Missing-Aspect Acquisition and Persistence

- [x] 4.1 Implement non-chat-time acquisition that accepts composite taxonomy, complete `required_aspects`, and missing-only `acquisition_aspects`, then searches only the missing subset within policy bounds.
- [x] 4.2 Reuse trusted-source validation, safe page fetching, and final combined judging without adding arbitrary crawling or deterministic semantic gates.
- [x] 4.3 Map acquisition with no accepted support to internal `insufficient`; preserve aggregate `partial` only when final judging accepts at least one required aspect.
- [x] 4.4 Build immutable content documents, individual aspect-support associations, and validation-run records with their explicitly owned metadata while excluding full page bodies and generated profile prose.
- [x] 4.5 Make content documents, aspect associations, chunks, embeddings, and LlamaIndex pgvector nodes converge on separate stable identities across retries and lease loss.
- [x] 4.6 Keep source version as provenance/content identity rather than evidence eligibility, and preserve older records when source version or content hash changes.
- [x] 4.7 Add tests proving locally covered aspects are not searched, final judging evaluates all required aspects, unsupported/off-aspect/untrusted/insufficient/contradictory acquired content is not persisted, and accepted evidence is retrievable later.
- [x] 4.8 Add tests proving multi-aspect content is embedded once and policy or complete-aspect-set changes do not duplicate content, support associations, chunks, embeddings, or vector nodes.

## 5. Durable Enrichment Handler

- [x] 5.1 Add `enrich_confirmed_plant` to closed job contracts and register its supported payload version and handler in the existing worker registry.
- [x] 5.2 When normalized local judging covers every required aspect, establish final coverage from that result, short-circuit external acquisition, and record avoided acquisition.
- [x] 5.3 Implement bounded acquisition groups, final combined judging, idempotent evidence persistence, and final coverage calculation against all required aspects.
- [x] 5.4 Map full coverage to `complete`, useful subset coverage to `partial`, successful no-support to non-retryable `failed` with `insufficient_evidence`, retryable operational failures to retry then `failed`, and permanent contract failures directly to `failed`.
- [x] 5.5 Ensure terminal `complete`, `partial`, and `failed` transitions release active uniqueness atomically without weakening permanent run idempotency.
- [x] 5.6 Add handler tests for empty installation, covered species, partial support, acquired completion, insufficient evidence, safety rejection, retry success, exhaustion, lease-loss replay, unsupported versions, and duplicate prevention.

## 6. Transactional Confirmation and Authorization

- [x] 6.1 Refactor candidate confirmation so repository mutation does not commit internally and confirmation orchestration owns one request transaction.
- [x] 6.2 Enforce validated composite taxonomy, enqueue or reuse only active shared work, and persist the owner/candidate/current-policy association before confirmation commit.
- [x] 6.3 Make same-candidate same-policy replay return its existing association, and make a candidate with only older-policy associations create or join current-policy work.
- [x] 6.4 Allow an eligible confirmation with no current-policy association to create a new run after prior equivalent jobs become terminal.
- [x] 6.5 Return temporary unavailability and roll back when durable scheduling fails; never commit confirmation without its job and association.
- [x] 6.6 Add authenticated applicable-status reads that expose bounded lifecycle/results to the candidate owner and return identical not-found behavior for unknown or foreign candidates.
- [x] 6.7 Add PostgreSQL/API tests for atomic commit/rollback, unavailable scheduling, invalid identity, same-policy replay, policy upgrade, cross-owner active sharing, terminal new runs, restart durability, and ownership isolation.

## 7. Profile and Frontend Contracts

- [x] 7.1 Extend profile responses with applicable enrichment metadata while always returning the latest persisted profile snapshot for every job state without introducing section regeneration.
- [x] 7.2 Ensure snapshot sections and sources represent only evidence used to create that snapshot and remain distinct from enrichment outcomes and current assistant-retrievable evidence.
- [x] 7.3 Regenerate the backend OpenAPI baseline and frontend TypeScript contracts, then add typed client/BFF operations for confirmation metadata, authorized status, and profile snapshot reads.
- [x] 7.4 Move `PlantProfileView` loading to TanStack Query, poll only `pending` or `processing`, and stop polling plus invalidate status/snapshot metadata on `complete`, `partial`, or `failed`.
- [x] 7.5 Render concise lifecycle, covered/missing, and limitation state while keeping profile navigation and existing garden actions available.
- [x] 7.6 Add frontend tests for immediate navigation, terminal-aware polling, policy-version status, metadata invalidation without regeneration claims, partial/failed outcomes, snapshot source separation, and contract privacy.

## 8. Observability, Rollout, and Verification

- [x] 8.1 Add enrichment metrics for avoided acquisition, completion time, and partial outcomes while reusing existing durable-job retry/failure telemetry and bounded logging safeguards.
- [x] 8.2 Document composite identity, policy version 1, explicit aspect-set flow, outcome mapping, compatible-worker-first rollout, mandatory confirmation scheduling, and forward recovery.
- [x] 8.3 Verify deployment and local worker configuration accept the new job type before confirmation scheduling is enabled, and ensure rollback keeps compatible enqueueing or temporarily disables confirmation.
- [x] 8.4 Add end-to-end coverage proving an empty confirmed species schedules enrichment, profile navigation remains available, accepted evidence reaches pgvector retrieval, and a later assistant request retrieves it.
- [x] 8.5 Add end-to-end covered, partial, insufficient, failed, retried, policy-upgraded, taxonomy-version-changed, source-version-changed, duplicate, and worker-restart scenarios with bounded status and preserved provenance.
- [x] 8.6 Run backend Ruff and unit/integration pytest suites, OpenAPI snapshot checks, frontend lint/typecheck/tests/build, and deployment rendering checks before rollout.
