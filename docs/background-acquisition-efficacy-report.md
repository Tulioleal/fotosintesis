# Background Acquisition Efficacy Report

Date: 2026-08-12 (post final verification of `complete-confirmed-plant-enrichment`)

## Executive Summary

The background acquisition feature is the confirmed-plant enrichment workflow
defined by the archived confirmed-plant enrichment spec, the offline
acquisition requirements, and the durable worker requirements, tracked in
`openspec/changes/complete-confirmed-plant-enrichment/`.

The production orchestrator is exercised end to end against PostgreSQL +
pgvector with deterministic provider-boundary fixtures. Source trust fails
closed; concurrent aspect mutation and vector refresh serialize under a
document row lock; the assistant trusted-first fallback routes source support
through caller-scoped eligibility; every support item carries exactly one raw
canonical source URL; enrichment jobs finalized after migration 0012 produce
exactly one immutable durable observation; renewal cannot report lease loss
after a committed terminal outcome; and the deterministic efficacy corpus runs
every case through the real `EnrichConfirmedPlantHandler` (not the full
worker), including a genuine policy v1-to-v2 case, a genuine source-version
change, and a genuine content-hash change. Durable worker execution is
verified separately by the confirmation-to-worker and terminal-observation
tests. The corpus reports 33 accepted aspects, 31 coverage gain, and exact
bidirectional vector/relational cardinality with zero unsupported persistence,
zero duplicate effects, and zero effect mismatches.

## Verification Environment

| Component | Version |
| --- | --- |
| Git SHA (pre-change baseline) | `9c24542f9e192505e6b0a1f635f40cd4428ad0ea` |
| Worktree state | 34 modified and 12 untracked files total, including this report and the change artifacts |
| Python | 3.12.13 |
| pytest / pytest-asyncio | 9.1.1 / 1.4.0 |
| SQLAlchemy | 2.0.51 |
| asyncpg | 0.31.0 |
| pydantic | 2.13.4 |
| llama-index-core | 0.14.23 |
| pgvector (Python package) | 0.5.0 |
| PostgreSQL | 16 (Debian, pgvector image) |
| Node / pnpm | 22.22.0 / 9.15.4 |
| ruff | 0.8.4 (repo dev dependency; `ruff check app/ tests/` passes) |

### Backend test prerequisites

`tests/run-in-container.sh` (from `backend/`) execs pytest inside the running
`photosynthesis-backend-1` container, whose PostgreSQL is the
`photosynthesis-postgres-1` container. It sets `TEST_DATABASE_URL` to the
`fotosintesis_test` database. That database must be a separate, unmigrated
database whose `public` schema has no application tables: per-test integration
schemas are created with `metadata.create_all`, which skips tables that
already exist in `public`. These are environment prerequisites, not
clean-checkout guarantees; the counts below were produced in this environment
on this worktree.

## Verification Commands and Results

Backend tests run inside the Python 3.12 container with
`sh tests/run-in-container.sh <pytest args...>` (from `backend/`) against a
clean PostgreSQL/pgvector test database whose `public` schema is intentionally
empty; integration tests create per-test schemas with `metadata.create_all`.

| Command | Result |
| --- | --- |
| `ruff check app/ tests/` | Passed |
| `sh tests/run-in-container.sh -q tests/test_observability_logging.py tests/test_provider_fallback_part1.py` | 53 passed, 0 skipped |
| `sh tests/run-in-container.sh -q tests/integration/test_enrichment_efficacy_corpus.py tests/integration/test_production_enrichment.py tests/integration/test_enrichment_aspect_convergence.py` | 35 passed, 0 skipped |
| `sh tests/run-in-container.sh -q tests/deployment/test_render_worker.py` | 67 passed, 0 skipped |
| `sh tests/run-in-container.sh -q tests/integration/test_migration_0012.py tests/integration/test_worker_observability.py tests/integration/test_worker_scenarios.py` | 69 passed, 0 skipped |
| `sh tests/run-in-container.sh -q tests --ignore=tests/integration --ignore=tests/deployment` | 696 passed, 0 skipped |
| `sh tests/run-in-container.sh -q tests/integration` (clean test database) | 202 passed, 0 skipped |
| `corepack pnpm --filter frontend lint` | Passed |
| `corepack pnpm --filter frontend build` | Passed |
| `corepack pnpm --filter frontend typecheck` | Passed |
| `corepack pnpm --filter frontend test` | 148 passed (28 files) |
| `corepack pnpm --filter frontend openapi:check` | Passed |
| `openspec validate "complete-confirmed-plant-enrichment" --strict` | Passed |
| `git diff --check` | Passed |
| `sh deploy/scripts/validate-job-switches.sh false true true` | Rejected (exit 1) |
| `sh deploy/scripts/validate-job-switches.sh true true true` | Rejected (exit 1) |
| `sh deploy/scripts/validate-job-switches.sh false false true` | Accepted (exit 0) |
| `sh deploy/scripts/validate-job-switches.sh true true false` | Accepted (exit 0) |

## Remediation Results

| Workstream | Result |
| --- | --- |
| Source-scoped evidence packages | `_bounded_evidence_sources` emits one judge package per supplied evidence package (no URL deduplication) with a stable `source_package_id`, preserving order, `MAX_JUDGE_SOURCES`, and the total character budget. Two packages sharing one URL both appear. |
| Raw one-URL cardinality | `_accepted_acquired_claims` and the assistant ingestion payload selector require the raw `source_urls` list to be exactly one non-empty string before any other validation; `["", url]`, `[url, url]`, `[url, other]`, and `[]` are all rejected. Deduplication is never the cardinality authority. |
| Fallback source binding | `_validated_answerability` routes through `normalized_coverage` with evidence and configured thresholds; `_judge_combined_evidence` builds one package per RAG chunk and trusted web result with explicit validation status, eligible only for `{"trusted", "external_fallback"}`, and passes source-separated `evidence_sources` to the judge. Unknown-URL and multi-URL fallback support is removed; trusted paraphrased support remains accepted without substring matching. |
| Fail-closed source trust | Production enrichment and normal RAG construct evidence eligible only for `trusted`; `external_fallback` is rejected by both. Only the assistant trusted-first fallback may opt into `external_fallback`, and missing/blank/unknown statuses still fail closed. |
| Two-phase convergence | Phase A persists relational support and chunk metadata; Phase B reacquires the document lock, reloads authoritative relational aspect support, associates the validation, upserts stable vector nodes, commits once, and rolls back on any `BaseException`. A retry after relational commit and vector failure converges without duplicates; concurrent Phase B operations converge to the relational union without a third repair call. |
| Durable efficacy observations | Migration `0012_durable_enrichment_telemetry` creates the immutable observation table with closed labels, bounded counts, finite durations, an insert trigger verifying the referenced job is a terminal enrichment job with a matching outcome, and UPDATE/DELETE triggers rejecting mutation. A deferred constraint trigger on `application_jobs` requires exactly one matching observation for every new terminal enrichment transition. PostgreSQL enforces observation validity, uniqueness, immutability, and existence for new terminal enrichment transitions, while the application terminal paths (worker complete/partial/failed finalization and exhausted-job reconciliation) enforce observation creation. No historical backfill is performed: the deferred trigger governs only transitions after installation, and historical terminal jobs are neither backfilled nor rejected. The repository validates every count (integers, not booleans), the finite non-negative duration, and the closed label/outcome before issuing SQL. For jobs finalized after migration 0012, exactly one observation is inserted atomically with each complete/partial/failed terminal transition; retries and non-enrichment jobs produce none. Exhausted enrichment jobs with missing, string, boolean, zero, negative, or unknown positive policies each emit exactly one `"unsupported"` failed observation. |
| Renewal/finalization serialization | Renewal runs the complete operation under `transition_lock` and returns silently when finalization committed a terminal state; complete, partial, and failed finalization set `terminal_committed` after commit. Forced race tests for complete, partial, and failed outcomes prove no `worker_lease_lost` log, no generic `lease_lost` metric, one terminal generic outcome, one durable observation, and no cancelled handler. |
| Readiness and deployment safety | `_refresh_durable_efficacy_metrics` propagates errors during readiness establishment (enabled reconciliation and disabled pause health) so a failing telemetry query keeps readiness `503`; failures after committed terminal jobs only log. Enabled and disabled workers stay `503` and recover to `200`. A disabled default worker validates its required contracts against the static production payload catalog (`get_production_payload_model`) without constructing handlers or providers and becomes ready without registering handlers; an unsupported required contract keeps it `503`. The deploy validator is closed and unambiguous: every input must be exactly `true` or `false`, paused deployments require both switches disabled, worker-enabled deployments require `paused=false`, and the worker readiness gate verifies `JOBS_WORKER_ENABLED=true` plus `enrich_confirmed_plant:1`. The readiness condition negates the Boolean `paused_deployment` input (`if: ${{ !inputs.paused_deployment }}`); GitHub Actions preserves the input type, so the expression never compares it with a string. |
| Real policy-change corpus case | Every corpus case runs through `EnrichConfirmedPlantHandler.handle()` (the real handler, not the full worker). The policy-change case executes policy v1 then test-only policy v2 (which adds `pot_drainage` and a distinct policy `semantics_fingerprint`); policy v2 is resolved via a test-only resolver and a temporary patch of `app.enrichment.policy.get_enrichment_policy`, and the production policy registry is never altered. `acceptance_semantics` contributes to the immutable policy semantics fingerprint; the executable v2 difference exercised by the corpus is the required-aspect set, not a pluggable acceptance algorithm. The run reuses the existing document/chunk/embedding/vector identity, gains one additional aspect-support row, gains the new aspect in vector metadata, and returns the original chunk ID for retrieval by the new aspect. Test policy v2 is deliberately not routed through durable telemetry, whose labels support only released policy 1. |
| Source-change corpus case | The corpus contains a genuine source-version change and a genuine content-hash change across three runs. Run 1 (`s8`) and run 2 (`s8-v2`) share the same accepted claim/quote content: equal normalized content hashes but different source versions and different stable document, chunk, and vector node identities. Run 3 keeps `s8-v2` with a visibly different, non-empty, accepted quote: the same source version but a different normalized content hash and document identity. All three remain retrievable by their accepted aspects. Content change and source-version change remain independently covered. |
| Complete per-run effect snapshots | Before and after every corpus run a shared `EffectSnapshot` captures document/source/chunk/embedding IDs, `(document_id, aspect)` support pairs, validation-evidence association pairs, validation-run IDs, and every pgvector node ID. Each run asserts document, source, chunk, embedding, and vector-node cardinality deltas equal the expected document delta; stable identity sets are monotonic (nothing is ever removed); relational support, relationally refreshed chunk metadata, and vector node metadata must fully agree for every chunk after every run; newly persisted support aspects are all accepted by that run (even globally canonical aspects count as unsupported otherwise); exactly one validation run is recorded per service execution; and one-source runs associate exactly one validation with accepted evidence or none otherwise. |
| Full vector cardinality | A test-only helper queries the vector store table directly and compares the complete vector node ID set against relational chunk IDs after corpus execution, retry convergence, concurrent convergence, replacement-worker convergence, and rejected-evidence snapshots. |
| Safety-only zero effect | A safety-only run whose only support is below the safety threshold produces zero documents, sources, chunks, embeddings, aspect supports, validation-evidence associations, or vector nodes; `covered_aspects` is empty, the safety aspect remains missing, and `safety_evidence_rejected` is true. The existing mixed watering-plus-safety case is retained. |
| Source-identity-free telemetry | Page-fetch logs carry only bounded operational fields (fetch status, closed error category, error type, content/snippet lengths, duration, trace id); the raw URL, source domain, and URL hash are removed. Provider configuration failures log the closed role, provider name, and exception type only, never the exception string. The JSON log formatter suppresses `exc_info` and emits only the closed `error_type` name, so provider prompts, payloads, evidence bodies, and species values cannot leak through exceptions; the formatter does not redact arbitrary application-authored `ctx_error` fields. |
| Metric contract and privacy | Exact label keys and closed values, exact observation counts and histogram sums, and real durable-job sensitive values (idempotency key, serialized payload, provenance id, species name/key, GBIF key, URL/domain, claim, quote, source body, rubric sentinel) absent from rendered Prometheus output and structured logs. The real run ID appears only in the bounded `ctx_job_id` operational field, never in metric labels, message text, or any other `ctx_*` field. `lease_lost` is removed from enrichment lifecycle outcomes and never produces an efficacy observation. |
| Durable restart | A worker restart reconstructs the same database-derived efficacy totals without incrementing them; generic process-local metrics reset on restart while durable efficacy is reconstructed from PostgreSQL, so replicas expose identical totals and monitoring aggregates with `max`, not `sum`. |

## Efficacy Corpus Metrics (deterministic, real handler + PostgreSQL/pgvector)

The corpus executes every case through `EnrichConfirmedPlantHandler.handle()`
(not the full worker); durable worker execution is verified separately by the
confirmation-to-worker and terminal-observation tests.

| Metric | Value |
| --- | --- |
| Total runs | 15 |
| Lifecycle distribution | complete 2, partial 9, failed 4 |
| Acquisition avoided | 1 (local-complete case) |
| Accepted aspects (snapshot `accepted_aspect_count`) | 33 |
| Coverage gain (snapshot `coverage_gain`) | 31 |
| Final documents / sources / chunks / embeddings | 9 / 9 / 9 / 9 |
| Relational aspect-support rows | 33 |
| Full vector-table node IDs | 9 (exactly equal to relational chunk IDs) |
| Unsupported persistence | 0 (every newly persisted support aspect is accepted by its run) |
| Duplicate effects | 0 (no unexpected positive cardinality delta for documents, sources, chunks, embeddings, supports, validation associations, or vector nodes) |
| Effect mismatches | 0 (no shortfall, validation-run, or validation-association mismatch) |
| Maximum searches per run | Configured/asserted upper bound: `<= 6` (`search_count_max` corpus assertion; policy v2 exercises six search groups) |
| Later aspect-filtered retrieval failures | 0 |
| Policy versions exercised | 1 (released) and 2 (test-only, added `pot_drainage`, distinct semantics fingerprint) |
| Safety-only rejected case | zero domain effects, `safety_evidence_rejected` true |

## Remaining Limitations

- Historical enrichment documents written before this change may carry stale
  vector metadata. The executed comparison used a synthetic production-like
  PostgreSQL/pgvector fixture: it proves touched content converges under the
  new code and does not inspect a live production dataset. A live drift query
  comparing `knowledge_document_aspect_supports` with pgvector node
  `covered_aspects` remains a pre-deployment operational gate; content touched
  by the new code converges without a separate repair operation, and re-running
  the affected validations repairs touched content. No automatic backfill was
  added.
- The corpus is deterministic and does not measure live answerability gains;
  production monitoring should track `fotosintesis_enrichment_efficacy_*`
  distributions, aggregating durable totals with `max` across replicas.

## Final Assessment

All acceptance gates pass: ruff, focused privacy/logging tests, the migration
suite (including the deferred observation-existence trigger), the full backend
unit suite on Python 3.12, the full PostgreSQL/pgvector integration suite
against a clean test database, the deployment and switch-validation suites, the
frontend lint/typecheck/tests/OpenAPI/build gates, `git diff --check`, and
`openspec validate "complete-confirmed-plant-enrichment" --strict`. Every
support item carries exactly one raw canonical URL; no fallback path bypasses
source binding; page-fetch, provider-configuration, and exception logs carry no
source identity or exception content (the formatter emits only the exception
type); every enrichment job finalized after migration 0012 has exactly one
immutable durable observation enforced by PostgreSQL, and a new terminal
transition without a matching observation rolls back; retries and malformed
exhausted jobs use `"unsupported"`; telemetry query failure keeps readiness
false; renewal cannot report lease loss after a committed terminal outcome; a
genuine v1-to-v2 policy change runs with different required aspects and a
distinct semantics fingerprint through the real handler (not a pluggable
acceptance algorithm); the corpus contains a real source-version change and a
real content-hash change; complete per-run effect snapshots compare relational
support, chunk metadata, and vector metadata after every run and detect
duplicates, unsupported persistence, removals, and aspect divergence; the full
pgvector node set equals the relational chunk set; the real run ID appears only
as the bounded `ctx_job_id` field; safety-only rejected evidence has zero
effects; invalid deployment switches fail before any migration; the paused
readiness condition uses the Boolean input; and rollback documentation covers
migration 0012.
