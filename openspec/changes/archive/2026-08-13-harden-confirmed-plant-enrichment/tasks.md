## 1. OpenSpec Change Organization

- [x] 1.1 Create the `harden-confirmed-plant-enrichment` proposal, design, delta specifications, and task list with an explicit proposal-11 non-goal.
- [x] 1.2 Restore only the remediation additions currently made directly to the five main specs after confirming equivalent delta requirements exist; do not reset unrelated work and do not synchronize main specs before archive.
- [x] 1.3 Validate this active change strictly and keep `refresh-profiles-from-evidence` untouched.

## 2. Durable Accepted Progress

- [x] 2.1 Make useful coverage equal accepted local coverage plus persisted accepted aspects so judge-only coverage cannot produce a false partial.
- [x] 2.2 Lock progress rows for every read-merge-write update and for live and reconciled terminal decisions.
- [x] 2.3 Add focused regression tests for judge-only failure, persisted operational partial, and concurrent accepted-aspect union.
- [x] 2.4 Run focused Ruff, enrichment unit tests, PostgreSQL convergence tests, and `git diff --check` for the critical progress fix.
- [x] 2.5 Use checkpoint-derived efficacy consistently for normal complete, normal semantic partial, failure-derived partial, and failed enrichment terminal observations.
- [x] 2.6 Select `indexing_deferred`, `retry_exhausted`, or `workflow_incomplete` from the actual unfinished stage and use enqueue-to-terminal duration consistently.
- [x] 2.7 Add focused tests comparing every terminal observation with durable checkpoint counts and proving reconciled partial work records a generic partial outcome.

## 3. Balanced Retrieval and Fetched Evidence

- [x] 3.1 Verify per-aspect retrieval requires validation provenance for the current requested aspect, not merely another requested aspect covered by the same chunk.
- [x] 3.2 Preserve coverage-balanced ordering through the production local semantic judge budget and add a regression with unrelated higher-scoring chunks.
- [x] 3.3 Keep confirmed enrichment fetched-content-only and prove snippet-only timeout, unsupported-content, oversized, and unsafe-redirect cases have zero domain and vector effects.
- [x] 3.4 Ensure the academic trusted fetch path reads at most the configured response limit plus one byte and retains HTTPS, approved-domain, redirect, timeout, and content-type checks.
- [x] 3.5 Simplify or remove production-grade DNS-pinning and peer-verification requirements and implementation if they are not needed by the bounded academic contract; do not weaken the basic trusted fetch gates.
- [x] 3.6 Keep source identity deterministic for basic equivalent HTTPS forms without rewriting historical evidence, and add focused path/query distinction tests.
- [x] 3.7 Add or retain multilingual, synonym, and paraphrased evidence regressions that reach semantic judging without keyword, regex, translated-term, substring, or token-presence gates.

## 4. Canonical Candidate and Assistant Handoff

- [x] 4.1 Preserve server-resolved confirmed candidate canonical identity when garden context loading selects a different display-matched plant.
- [x] 4.2 Add a real graph-path regression where candidate species A conflicts with a display hint matching garden species B and retrieval remains species A.
- [x] 4.3 Add frontend tests proving identification and profile assistant links include candidate ID, binomial, and full scientific context.
- [x] 4.4 Add an `AssistantChat` test proving the candidate query parameter maps to `confirmed_candidate_id`, and update plant-only exact payload expectations for the optional field.
- [x] 4.5 Preserve owner, confirmation, and taxonomy validation checks and prove unauthorized or invalid candidate context never supplies canonical retrieval identity.

## 5. Canonical Profiles Without Refresh

- [x] 5.1 Align migration `0014` canonical identity validation with runtime positive-GBIF-key and normalized-binomial rules, leaving ambiguous controlled data unchanged.
- [x] 5.2 Make concurrent canonical profile creation converge by handling the unique-key race and reselecting the winning profile.
- [x] 5.3 Stop runtime adoption of ambiguous null-key legacy profiles based only on display-name equality; document controlled academic migration assumptions.
- [x] 5.4 Restrict new profile snapshot evidence to matching canonical identity, trusted provenance, eligible review state, accepted individual aspect support, and applicable validation provenance.
- [x] 5.5 Add tests excluding unsupported or incompletely validated canonical documents and including accepted canonical evidence.
- [x] 5.6 Replace the current proposal-11 boundary test with a seeded existing snapshot whose sections, sources, confidence, and limitations remain exactly unchanged after enrichment while assistant retrieval succeeds and no refresh job is created.

## 6. Bounded and Accessible Profile Status

- [x] 6.1 Replace `job.updated_at` stall detection with a candidate-and-job-scoped client observation deadline that identical active responses and lease renewals cannot extend indefinitely.
- [x] 6.2 Reset delayed state immediately when candidate or job ID changes, and stop polling permanently on terminal status.
- [x] 6.3 Disable manual `Revisar estado` while refetching, render checking text, issue one request per activation, and preserve focus.
- [x] 6.4 Add distinct Spanish UI copy and component assertions for `retry_exhausted`, `workflow_incomplete`, and `indexing_deferred`.
- [x] 6.5 Add focused tests for one polite live region, alert semantics, no duplicate status nodes, keyboard activation, retained profile actions, context switching, and the bounded observation window.
- [x] 6.6 Keep accessibility automation proportional to the academic scope and do not claim every lifecycle state is covered unless each state is explicitly arranged and scanned.

## 7. Contracts, Traceability, and Documentation

- [x] 7.1 Regenerate backend OpenAPI and frontend generated contracts only after backend profile and assistant schemas stabilize.
- [x] 7.2 Update `docs/proposal-02-traceability.md` with exact executable test names, the completed progress regressions, honest pending statuses, and explicit production-hardening deferrals.
- [x] 7.3 Update worker operations documentation: judge-only coverage is not durable progress; partial exhaustion means accepted progress survived; failed exhaustion means none survived; terminal jobs are not reset in place.
- [x] 7.4 Document that policy v1 has no age-expiry or source-supersession behavior and that adding either requires a new policy version.
- [x] 7.5 Confirm generated clients and UI never expose raw progress rows, job payloads, evidence content, or another owner's candidate existence.

## 8. Verification and Archive Gate

- [x] 8.1 Run backend Ruff and focused progress, jobs, assistant, profile, trusted-fetch, migration, PostgreSQL/pgvector, status, and proposal-11 boundary tests.
- [x] 8.2 Run the complete backend unit and integration suites in the project Python 3.12 PostgreSQL/pgvector environment.
- [x] 8.3 Run frontend lint, typecheck, focused component tests, full tests, build, OpenAPI check, and the bounded enrichment journey.
- [x] 8.4 Run `openspec validate "harden-confirmed-plant-enrichment" --strict` and `git diff --check`.
- [x] 8.5 Review the final diff for accidental profile regeneration, refresh-job scheduling, main-spec synchronization before archive, or other proposal-11 behavior.
- [x] 8.6 Verify the completed change against proposal, design, delta specs, and tasks before archiving.
- [x] 8.7 Archive and synchronize the verified change before starting proposal 11.
