## 1. Semantic Support Binding

- [x] 1.1 Add regression tests where multilingual and paraphrased final-judge support is source-bound but its evidence quote is not an exact substring of the supplied source text.
- [x] 1.2 Refactor semantic source-support binding to validate requested canonical aspects, supplied canonical source identity, trust status, non-empty claim and quote, and safety confidence without lexical semantic gates.
- [x] 1.3 Update enrichment accepted-claim selection to consume normalized source-bound support without reapplying exact quote containment.
- [x] 1.4 Add negative tests proving unknown sources, malformed support, unrequested aspects, untrusted sources, and safety support below threshold remain excluded from persistence.
- [x] 1.5 Run assistant semantic-coverage and enrichment regression suites to confirm chat-time and offline behavior remain coherent.

## 2. Relational and Vector Aspect Convergence

- [x] 2.1 Add a PostgreSQL/pgvector regression test where unchanged existing enrichment content gains a newly accepted aspect and becomes retrievable through that aspect filter.
- [x] 2.2 Reload authoritative enrichment evidence state after idempotent aspect-association writes and before returning state for vector upsert.
- [x] 2.3 Ensure stable-node vector upsert replaces mutable `covered_aspects` metadata with the complete relationally accepted canonical aspect set.
- [x] 2.4 Add retry coverage for failure after relational aspect commit but before vector metadata refresh, asserting no duplicate documents, supports, chunks, embeddings, or vector nodes.
- [x] 2.5 Add a concurrent validation test proving different accepted aspects converge to the relational and vector union for one stable content identity.

## 3. Production Enrichment Integration

- [x] 3.1 Build deterministic provider-boundary fixtures for search, trusted page evidence, semantic judging, and low-dimensional embeddings while retaining real production orchestration, repositories, and vector indexing.
- [x] 3.2 Add a direct PostgreSQL/pgvector test of `ProductionEnrichmentService.execute()` for empty local evidence, missing-aspect acquisition, final judging, evidence and validation persistence, and terminal coverage.
- [x] 3.3 Add a full confirmation-to-worker test that schedules `enrich_confirmed_plant`, executes the production handler, and retrieves accepted evidence through the production aspect-filtered retrieval path.
- [x] 3.4 Add production-path tests proving complete local evidence avoids search/fetch and records acquisition avoidance.
- [x] 3.5 Add production-path exclusion tests for untrusted, off-aspect, unsupported, contradictory, and safety-inadequate acquired evidence with zero knowledge/vector effects.
- [x] 3.6 Add production retry tests for provider and vector failures, including worker replacement after lease expiry, and assert stable convergent effects.
- [x] 3.7 Add policy-change and source-content-change tests proving unchanged content is reused while changed source version or content hash preserves a new auditable content version.

## 4. Efficacy Measurement

- [x] 4.1 Define bounded enrichment metric contracts for acquisition avoidance, local covered count, final covered count, coverage gain, accepted aspect count, search count, lifecycle outcome, and completion duration.
- [x] 4.2 Emit efficacy metrics from terminal production enrichment paths using only closed enums, booleans, bounded count buckets, policy version, and duration histograms.
- [x] 4.3 Add metric privacy tests proving species names, taxonomy keys, URLs, domains, claims, quotes, source bodies, prompts, payloads, and idempotency keys never appear in labels or structured logs.
- [x] 4.4 Create a deterministic efficacy corpus covering empty, sparse, complete, contradictory, multilingual, safety-sensitive, retry, policy-change, and source-change cases.
- [x] 4.5 Report acquisition avoidance, accepted coverage gain, unsupported persistence, duplicate effects, search bounds, lifecycle distribution, and later aspect-filtered retrieval success for the corpus.
- [x] 4.6 Add explicit efficacy assertions that unsupported persistence and duplicate effects remain zero and that every accepted indexed aspect is retrievable in the deterministic corpus.

## 5. Worker Readiness and Lease-Loss Observability

- [x] 5.1 Add a worker startup test proving the private readiness listener returns unavailable while provider dependency validation is slow or invalid.
- [x] 5.2 Refactor worker startup so the readiness/metrics listener starts before dependency validation and readiness remains false until validation plus durable reconciliation succeed.
- [x] 5.3 Prevent `Worker` from registering or constructing global production handlers when an explicit handler registry is supplied.
- [x] 5.4 Add recovery coverage proving readiness transitions to available after dependencies and reconciliation recover without restarting the worker.
- [x] 5.5 Replace lease-loss tests that poll transient private execution state with assertions on durable lease ownership, stale-finalization suppression, and one bounded lease-loss event or metric.
- [x] 5.6 Verify lease-loss cleanup remains prompt and does not retain completed execution state solely for observability.

## 6. Verification and Documentation

- [x] 6.1 Update the background acquisition efficacy report with post-change requirement status, test counts, corpus metrics, and remaining limitations.
- [x] 6.2 Run backend Ruff and focused semantic, enrichment, job, worker, PostgreSQL, pgvector, migration, status authorization, observability, and deployment tests.
- [x] 6.3 Run the complete backend unit and integration suites in the project Python 3.12 environment against a clean PostgreSQL/pgvector test database.
- [x] 6.4 Run OpenAPI snapshot checks and frontend lint, typecheck, tests, and build to verify no contract regression.
- [x] 6.5 Compare relational enrichment aspect associations with vector-node `covered_aspects` in a production-like dataset and document whether a separate bounded repair operation is required.

## 7. Verification Remediation

- [x] 7.1 Make source trust fail closed: only explicit `trusted` or permitted `external_fallback` validation statuses qualify, with blank, missing, or unknown statuses rejected in semantic binding and accepted-claim selection.
- [x] 7.2 Filter by `covered_aspect` before pgvector top-k with one bounded query per requested aspect, deduplicating by stable chunk ID and preserving requested-aspect order.
- [x] 7.3 Serialize concurrent aspect mutation and vector refresh: lock the stable knowledge document with PostgreSQL `FOR UPDATE`, reload authoritative relational aspects, and index from the freshly loaded state without a later repair call.
- [x] 7.4 Make global handler construction recoverable: synchronous construction runs off the event loop and is retried while readiness stays `503` and no jobs are claimed.
- [x] 7.5 Move efficacy telemetry to durable finalization: the handler attaches a bounded snapshot; the worker emits exactly one observation after complete, partial, or final failure commit and none for retries; exhausted enrichment jobs emit one failed observation after reconciliation commit.
- [x] 7.6 Consolidate lease-loss reporting into one idempotent path emitting one canonical warning and one bounded outcome per execution.
- [x] 7.7 Prove zero relational and vector effects for every rejected evidence case with complete before/after effect snapshots.
- [x] 7.8 Correct the efficacy corpus: report exact accepted-aspect total 33 and coverage-gain total 31 with exact final cardinalities after adding the content-hash-change run.
- [x] 7.9 Add exact metric contract and privacy assertions: the real durable job's run ID appears only in the bounded `ctx_job_id` operational field and never in metric labels, messages, or arbitrary telemetry fields; idempotency key, payload, provenance ID, and evidence content appear nowhere.
- [x] 7.10 Add real content-hash-change coverage proving claim/quote content and source version are independent identity dimensions.
- [x] 7.11 Add replacement-worker cardinality coverage proving convergent domain effects after lease replacement.
- [x] 7.12 Stabilize the lease-renewal unit timing test with a started event.
- [x] 7.13 Reproduce the full verification order and correct the efficacy report with exact commands, versions, counts, and corpus totals.

## 8. Remediation: Source-Scoped Evidence And Durable Telemetry

- [x] 8.1 Source-separated evidence packages with exactly one canonical source URL per support item, and one source package per supplied evidence package.
- [x] 8.2 Caller-scoped trust eligibility: production enrichment and normal RAG use only `trusted`; only the assistant trusted-first fallback may opt into `external_fallback`.
- [x] 8.3 Two-phase document-lock convergence clarification in the design and tests proving Phase B reloads authoritative relational state.
- [x] 8.4 Durable terminal efficacy observations stored in PostgreSQL, atomically inserted with the terminal job transition.
- [x] 8.5 Renewal/finalization serialization so a successful finalization can never produce a false lease-loss event.
- [x] 8.6 Closed telemetry policy labels ("1" or "unsupported") with `lease_lost` removed from enrichment lifecycle outcomes.
- [x] 8.7 Real policy-version-change corpus coverage exercising genuinely different required aspects and a distinct policy semantics fingerprint.
- [x] 8.8 Complete pgvector cardinality assertions where every vector node ID is compared with relational chunk IDs.
- [x] 8.9 Safety-only zero-effect coverage proving rejected safety evidence changes nothing.
- [x] 8.10 Disabled-worker readiness clarification and deployment protection separating disabled pause health from active-consumer readiness.
- [x] 8.11 Documentation and efficacy-report corrections replacing unsupported claims with measured results.
- [x] 8.12 Full verification rerun (Ruff, unit, integration, frontend, OpenAPI, OpenSpec verification).

## 9. Final Remediation

- [x] 9.1 Static production payload contract catalog (`PRODUCTION_PAYLOAD_MODELS` and `get_production_payload_model`) used by `register_handlers` and by disabled workers that validate required contracts without constructing handlers or providers.
- [x] 9.2 Disabled-worker regression tests: a disabled default worker becomes ready without registering handlers or constructing providers and validates `enrich_confirmed_plant:1`; an unsupported required contract keeps it `503`.
- [x] 9.3 Preserve explicit falsey handler registries (`handler_registry if handler_registry is not None else get_handler_registry()`).
- [x] 9.4 Closed and unambiguous deployment switch validation: inputs must be exactly `true`/`false`, paused requires both switches disabled, worker-enabled requires `paused=false`, with an expanded rejection matrix and workflow-text comment.
- [x] 9.5 The unknown-source production test is real: the deterministic judge emits support for an unsupplied URL via `emit_unsupplied_support`, and the test asserts the raw judge result contains it while final covered aspects and all knowledge/vector effects stay empty.
- [x] 9.6 Correct task 7.8 to the executable corpus totals: accepted-aspect 33 and coverage-gain 31 after adding the content-hash-change run.
- [x] 9.7 Align migration recovery documentation: no backfill, no routine database downgrade, telemetry-compatible prior image or forward fix, downgrade only for controlled development/test teardown with explicit approval.
- [x] 9.8 Direct requested-aspect ordering coverage for `_retrieve_enrichment_chunks` with one vector query per distinct aspect.
- [x] 9.9 Efficacy report made reproducible with exact commands, passed/skipped counts, and bounded search wording.
- [x] 9.10 Full verification rerun (focused suites, deployment combinations, Ruff, unit, integration, frontend, OpenAPI, OpenSpec verification).

## 10. Final Verification Corrections

- [x] 10.1 Remove source identity and exception content from enrichment telemetry.
- [x] 10.2 Enforce one observation for every new terminal enrichment transition in PostgreSQL.
- [x] 10.3 Correct source-change and policy-change efficacy corpus execution.
- [x] 10.4 Compare complete per-run relational and vector effects in the efficacy corpus.
- [x] 10.5 Validate deployment switches before applying migrations.
- [x] 10.6 Correct rollback and efficacy documentation.
- [x] 10.7 Run and record all verification gates.

## 11. Final Archive Remediation

- [x] 11.1 Remove exception strings from provider configuration logs and add sentinel privacy tests.
- [x] 11.2 Make the efficacy corpus compare complete relational aspect state with complete vector metadata after every run.
- [x] 11.3 Add a real content-hash-change run to the deterministic efficacy corpus.
- [x] 11.4 Correct policy-change claims to the behavior actually exercised.
- [x] 11.5 Correct the paused-deployment Boolean condition and regression test.
- [x] 11.6 Remove the unfinished duplicate replacement-path test block.
- [x] 11.7 Correct efficacy documentation and rerun all verification gates.

## 12. Verification Documentation Corrections

- [x] 12.1 Update obsolete efficacy corpus totals in tasks 7.8 and 9.6.
- [x] 12.2 Correct the efficacy report worktree-file count description.
- [x] 12.3 Run final OpenSpec and diff validation.
