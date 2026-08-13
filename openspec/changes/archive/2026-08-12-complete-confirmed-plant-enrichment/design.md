## Context

The archived confirmed-plant enrichment change established atomic scheduling, canonical species identity, policy-bounded missing-aspect acquisition, semantic judging, relational evidence persistence, and durable worker execution. Verification found that these components exist, but the production `ProductionEnrichmentService.execute()` path is not tested as a whole.

Two implementation details weaken the intended behavior. First, normalized source support is discarded when a judge-provided evidence quote is not an exact substring of the combined evidence, even when the semantic judge coherently binds the support to a supplied source. Second, when existing content gains a newly accepted aspect association, persistence returns a state loaded before that association and can upsert stale `covered_aspects` into pgvector metadata.

Worker verification also exposed startup and lease-loss observability problems: global handlers are registered synchronously before the readiness listener starts even when an explicit registry was supplied, and one test depends on observing a transient private execution entry after lease-loss cleanup.

This change spans assistant semantic coverage, enrichment persistence, vector indexing, worker startup, observability, and PostgreSQL/pgvector integration tests. It must preserve multilingual semantic authority and must not introduce keyword, regex, translated-word, substring, or token-presence gates.

## Goals / Non-Goals

**Goals:**

- Bind final semantic source support to supplied trusted evidence without making exact quote containment the coverage authority.
- Ensure new aspect associations for existing content converge in both relational and vector metadata.
- Prove the real production enrichment path from confirmation through later retrieval.
- Measure bounded coverage gain and operational outcomes without leaking evidence content.
- Make worker readiness observable while dependencies are being validated.
- Verify lease loss through durable state and bounded events rather than private-map timing.

**Non-Goals:**

- No new crawler, trust policy, queue, provider, or profile regeneration flow.
- No fuzzy string similarity threshold, translated word list, language detector, or lexical substitute for semantic judging.
- No public exposure of claims, evidence quotes, source bodies, taxonomy strings, prompts, job payloads, or idempotency keys.
- No historical backfill or automatic revalidation of every existing enrichment document.
- No real external provider calls in deterministic CI efficacy tests.

## Decisions

### Decision 1: Separate semantic acceptance from provenance binding

The schema-validated final judge remains authoritative for aspect coverage. Deterministic binding will verify that each support item has canonical requested aspects, a non-empty claim and quote, a supplied canonical source URL, acceptable source validation status, and required confidence for safety aspects. It will not require the quote to be a literal substring of a combined evidence blob.

The acquisition package will retain source-scoped evidence packages: every supplied evidence package is a frozen `SemanticSourceEvidence` (text plus metadata) that keeps text and its source URL bound together, and each support item binds to exactly one supplied canonical source URL. A support item with an unknown URL, malformed structure, unsupported aspect, or ineligible source status remains ineligible. Trust eligibility is caller-specific: production enrichment and normal assistant RAG construct evidence eligible only for `trusted`; only the assistant trusted-first fallback path may construct evidence eligible for `trusted` and `external_fallback`, and `external_fallback` is never globally trusted.

Alternative considered: fuzzy quote matching. Rejected because a similarity threshold is another lexical semantic gate, is language-sensitive, and can bind a quote to the wrong source.

### Decision 2: Serialize aspect mutation and vector refresh under a document lock

Aspect persistence is two-phase because relational support must survive vector failure. Both phases lock the same stable knowledge document row with PostgreSQL `SELECT ... FOR UPDATE` and Phase B always reloads authoritative relational state. Each phase commits exactly once and one document is processed per transaction; locks for multiple documents are never held simultaneously.

**Phase A (relational persistence):**
lock document -> persist aspect union -> update relational chunk metadata -> commit

**Phase B (vector convergence):**
reacquire document lock -> reload authoritative aspect union -> associate validation -> stable vector upsert -> commit

Vector storage uses a separate transaction from the relational persistence of Phase A, so convergence depends on stable identities, idempotent upsert, authoritative reload, and durable retry. The vector metadata set must equal the relational accepted aspect-support set after each successful attempt. A retry after relational commit or vector failure repeats the reload and converges without duplicate rows or nodes. Holding the document lock during vector upsert is intentional and is the only cross-process serialization point; an in-process `asyncio.Lock` would not protect separate workers. The design makes no claim that relational and vector operations share one atomic database transaction.

Alternative considered: mutate the previously loaded in-memory state. Rejected because repository state is the concurrency authority and another transaction may have added associations.

### Decision 3: Test the production orchestrator with deterministic providers

Integration tests will instantiate the real production enrichment service and worker handler against a unique PostgreSQL schema and real LlamaIndex pgvector store. Search, page fetch, judge, and embedding providers will be deterministic fakes at provider boundaries, not replacements for the orchestration, persistence, repository, or vector-index classes under test.

The principal end-to-end test will confirm a validated candidate, claim and execute the real durable job, acquire support for missing aspects, persist validation/evidence records, complete or partially complete with bounded metadata, and retrieve the new evidence through the production retrieval path. Separate scenarios cover local-complete avoidance, unsupported/contradictory exclusion, safety rejection, retry convergence, policy expansion, and source-content change.

Alternative considered: continue testing each service through fake repositories. Rejected because that approach did not expose stale vector metadata and cannot prove later retrieval.

### Decision 4: Define efficacy as bounded coverage and retrieval outcomes

Efficacy evaluation will use a deterministic fixture corpus representing empty, sparse, complete, contradictory, multilingual, safety-sensitive, retry, policy-change, and source-change cases. It will calculate accepted aspect count and coverage gain from the returned execution facts, plus search count, lifecycle outcome, duplicate effects, and later aspect-filtered retrieval success. The corpus includes both a source-version change and a content-hash change and, after every run, compares complete stable identity sets and relational/chunk/vector aspect mappings (relational document support equals both relationally refreshed chunk metadata and vector node metadata).

Runtime metrics use only closed job type, closed policy label, lifecycle outcome, acquisition-avoided flag, bounded counts, and duration buckets. Species names, URLs, domains, claims, quotes, source text, prompts, and arbitrary error values are prohibited labels. Terminal enrichment efficacy is a durable observation: exactly one immutable PostgreSQL row per terminal enrichment job, inserted atomically in the same transaction as the terminal job transition (complete, partial, or final failure), and never for retries or non-enrichment jobs. A deferred constraint trigger on `application_jobs` requires exactly one matching observation for every new terminal enrichment transition; because it is deferred, the worker's job-status update and observation insert in one transaction validate at commit. The trigger governs only transitions after installation and performs no historical backfill, so historical terminal jobs are neither backfilled nor rejected. Exhausted enrichment jobs receive one failed observation in the same reconciliation transaction that exhausts them. Worker restarts reconstruct metrics from PostgreSQL so multiple replicas expose identical database-derived totals and monitoring must aggregate with max, not sum. One idempotent lease-loss observation is emitted when ownership loss is proven; lease loss is a generic job outcome and is never a terminal enrichment efficacy outcome. No telemetry represents handler intentions before durable outcome. The efficacy corpus executes every case through the real `EnrichConfirmedPlantHandler` (not the full worker); the test-only policy v2 is resolved with a test-only resolver and a temporary patch of `app.enrichment.policy.get_enrichment_policy` only during the v2 call, and the production policy registry is never altered. `acceptance_semantics` contributes to the immutable policy semantics fingerprint; the executable v2 difference exercised by the corpus is the required-aspect set (`pot_drainage`), and the corpus does not claim pluggable acceptance algorithms.

Policy labels are closed: released policy 1 renders as the label `"1"` and unknown, malformed, or boolean policy versions render as `"unsupported"`. When future policies are released, their labels and the migration constraint must be updated together. Enrichment lifecycle outcomes are closed to `complete`, `partial`, and `failed`; `lease_lost` is removed from enrichment lifecycle outcomes and remains a generic job outcome.

Alternative considered: use live-provider quality as a CI gate. Rejected because it is non-deterministic, costly, and conflates provider drift with orchestration correctness.

### Decision 5: Start readiness transport before recoverable dependency validation

The worker will establish its private metrics/readiness listener before production dependency validation. Synchronous global handler construction and dependency validation run off the event loop through `asyncio.to_thread()` and are retried inside the worker poll loop, so slow or failing construction can neither block nor terminate readiness reporting.

**Enabled readiness** remains false until global handler construction succeeds, required contracts validate, provider dependencies validate, durable reconciliation commits, and the durable efficacy metrics refresh succeeds.

**Disabled readiness** is read-only pause health, not active-consumer readiness. A disabled worker verifies only that the metrics/readiness listener is running, required contracts validate against the static production payload catalog without constructing handlers or providers, PostgreSQL is reachable, job tables can be queried, and durable telemetry aggregates can be queried. It must not validate external providers, reconcile expired jobs, claim jobs, renew leases, or finalize jobs.

Deployment configuration distinguishes the two states and the switch validator is closed and unambiguous: every input must be exactly `true` or `false`; a paused deployment requires both switches disabled; a worker-enabled deployment requires `paused=false`; producer enabled plus worker disabled fails; both disabled is allowed only as an explicitly approved paused deployment; a normal deployment requires the worker enabled, the required enrichment contract present, and ready status. If an explicit registry is passed to `Worker`, startup will not register or construct global handlers, and a supplied registry is never mutated by the worker.

Alternative considered: increase fixed test sleeps. Rejected because it hides event-loop blocking and does not guarantee prompt readiness reporting on slower deployments.

### Decision 6: Observe lease loss through durable and bounded signals

Lease-loss behavior will be asserted using the persisted job lease owner/token/status plus closed metrics or captured structured events. Tests will not require a private `_executions` entry to remain after cancellation and cleanup. The worker must still cancel stale execution and must never finalize with a lost lease.

Alternative considered: retain completed execution state for a grace period. Rejected because it adds memory retention solely for tests and does not improve durable correctness.

## Risks / Trade-offs

- **Judge support could cite a supplied URL but fabricate a quote** -> Require schema-valid source-scoped support, trusted source identity, non-empty quote, semantic judge authority, and strict safety confidence; preserve the quote for audit without treating lexical containment as semantic proof.
- **Vector metadata refresh races with another aspect association** -> Reload after association commit and use stable-node upsert from the repository's complete accepted aspect set.
- **Integration tests become expensive** -> Keep one principal end-to-end path and a bounded scenario matrix with deterministic low-dimensional embeddings.
- **Metrics cardinality grows** -> Allow only closed enums, booleans, bounded integer buckets, policy versions, and duration histograms.
- **Readiness listener starts while configuration is invalid** -> It reports `503` and no work is claimed until dependencies and reconciliation pass.
- **Existing stale vector metadata remains** -> Retry or revalidation repairs touched content; a separate bounded repair command may be proposed later if production data requires backfill.

## Migration Plan

1. Add failing semantic non-substring and aspect-expansion convergence tests.
2. Implement source-scoped semantic binding and authoritative state reload before vector upsert.
3. Add bounded efficacy metrics and production integration fixtures.
4. Change worker startup ordering and explicit-registry behavior, then replace private-map lease-loss assertions.
5. Run unit, PostgreSQL/pgvector integration, migration, deployment, OpenAPI, frontend, and full backend checks.
6. Deploy workers before or with API code; apply migration `0012_durable_enrichment_telemetry` before enabling durable efficacy telemetry.

Migration `0012_durable_enrichment_telemetry` creates the immutable
 `enrichment_telemetry_observations` table with closed policy labels, bounded
 counts, finite durations, an insert trigger that verifies the referenced job
 is an enrichment job in a matching terminal status, and UPDATE/DELETE triggers
 that reject mutation. No historical telemetry backfill is performed: durable
 guarantees begin after migration `0012` is applied.

Migration `0012` has no historical backfill. Normal application rollback uses
a telemetry-compatible prior application image or a forward-fix migration;
operators must not downgrade the database during routine rollback. The Alembic
downgrade for `0012` exists for controlled development/test teardown only, and
it deletes durable telemetry history and any durable metrics created after
deployment, so it requires explicit operator approval. It never touches
knowledge documents, chunks, embeddings, aspect supports, or vector nodes.

Rollback restores the prior application image. Stable relational identities and vector node IDs remain compatible. If metadata refresh has already added aspects, rollback does not delete those valid associations or nodes.

## Open Questions

No blocking product decisions remain. Whether existing production enrichment documents need a one-time metadata repair depends on a pre-deployment query comparing relational aspect associations with vector-node metadata.
