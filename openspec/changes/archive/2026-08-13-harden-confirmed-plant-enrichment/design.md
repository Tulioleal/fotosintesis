## Context

The archived confirmed-plant enrichment changes already provide transactional confirmation scheduling, durable jobs, semantic coverage judging, trusted acquisition, evidence persistence, pgvector indexing, authorized status, and frontend polling. A later review found that incremental evidence commits were not represented in durable job progress, canonical identity was not preserved through every profile and assistant path, and the remediation requirements were added directly to main specs without an active change.

This is an academic project. The implementation must demonstrate coherent architecture, correctness, traceability, and focused tests, but it does not need production-scale migration repair, network transport pinning, or multi-replica operational guarantees. Botanical coverage remains semantic and multilingual; deterministic keyword, regex, translated-term, substring, and token-presence rules remain prohibited.

## Goals / Non-Goals

**Goals:**

- Finalize exhausted enrichment as `partial` only when accepted local or persisted evidence survived.
- Serialize progress updates and converge retries without losing accepted aspects.
- Ensure every requested canonical aspect can contribute local evidence before bounded semantic judging.
- Preserve server-authorized candidate identity through profiles, garden records, assistant entry, and retrieval.
- Build new profile snapshots only from accepted evidence while preserving existing snapshots exactly.
- Keep trusted acquisition bounded and persist only successfully fetched content.
- Stop unbounded frontend polling and expose accessible manual status refresh.
- Produce an active, verifiable OpenSpec change with honest requirement-to-test traceability.

**Non-Goals:**

- Regenerating, invalidating, replacing, versioning, or refreshing existing profile sections.
- Evidence fingerprints, profile section versions, profile-refresh jobs, or any implementation of `refresh-profiles-from-evidence`.
- Time-based evidence expiration, source supersession, or historical evidence rewriting.
- An explicit same-candidate failed-job rerun endpoint.
- Production duplicate-profile repair or historical progress backfill.
- Production-grade DNS pinning, peer-IP verification, multi-address failover, or complete RFC URL canonicalization.
- Replacing semantic judging with deterministic text matching.

## Decisions

### Decision 1: Accepted durable progress is distinct from judge output

One `enrichment_job_progress` row is stored per enrichment job. It records required aspects, semantically accepted local aspects, persisted accepted aspects, indexed aspects, final judge diagnostics, and bounded efficacy counts.

Useful accepted coverage is exactly the union of `local_covered_aspects` and `persisted_covered_aspects`. `final_judged_covered_aspects` remains diagnostic until source support passes accepted-claim selection and persistence. Judge-only coverage never changes a failed job into `partial`.

When accepted evidence is persisted but not fully indexed, exhaustion produces an operational `partial` with `indexing_deferred`. With no accepted useful coverage, exhaustion produces `failed`.

Alternative considered: use final judge coverage directly. Rejected because structural source binding or persistence can reject every judged support item.

### Decision 2: Progress mutations and terminal decisions are serialized

Every read-merge-write mutation locks the progress row with `FOR UPDATE`. Evidence Phase A updates persisted aspects in the same relational transaction as accepted evidence. Evidence Phase B updates indexed aspects in the same transaction as validation association and vector convergence. Live and crash-reconciled terminal decisions also lock the row.

Alternative considered: last-write-wins JSON updates. Rejected because concurrent claims can erase each other's accepted aspects.

### Decision 3: Local retrieval is balanced before semantic judging

Canonical enrichment evidence is retrieved once per requested aspect using canonical species identity, trust, review status, evidence type, and covered-aspect filters. Stable chunks are deduplicated and interleaved so every aspect with candidates contributes one result before any aspect contributes a second. Semantic judging remains the only authority for coverage.

Alternative considered: one global top-k query. Rejected because unrelated high-scoring chunks can displace required-aspect evidence before judging.

### Decision 4: Confirmed candidate identity is authoritative

The assistant accepts an optional confirmed candidate ID, resolves ownership, confirmation, validation, accepted GBIF key, and normalized binomial server-side, and stores that identity in graph state. A selected garden plant supplies canonical identity only when candidate-resolved state does not already contain it. Client taxonomy strings remain display and compatibility context.

Alternative considered: accept a client canonical key. Rejected because it bypasses ownership and taxonomy validation.

### Decision 5: Canonical profile identity does not imply profile refresh

Profiles store accepted GBIF key, normalized binomial, and canonical species key while retaining the accepted scientific name for display. New profile creation finds evidence by canonical identity and includes only trusted, eligible documents with accepted aspect-support and validation provenance. Concurrent creation converges by handling the canonical unique-key race and reselecting the winner.

Existing profile rows are never regenerated by enrichment. The boundary test seeds an existing snapshot, runs enrichment, proves later retrieval, and verifies that sections, sources, confidence, and limitations remain unchanged.

For academic migrations, only unambiguous legacy rows are backfilled. Ambiguous rows remain unchanged and controlled development/test databases may be recreated. No production merge framework is introduced.

### Decision 6: Confirmed enrichment persists fetched content only

Search snippets may continue to support the existing degraded assistant fallback, but confirmed-plant enrichment accepts only successfully fetched trusted page content. Trusted fetching requires HTTPS, approved domains before and after redirects, bounded redirects, timeout, supported content types, and reading at most the configured byte limit plus one byte for overflow detection.

Source URLs receive basic deterministic normalization sufficient for stable new evidence identity. Historical identities are not rewritten. Advanced DNS-pinned transport is outside the required academic contract and may be removed or retained only if it does not complicate or weaken the bounded fetch path.

### Decision 7: Frontend polling uses a client observation deadline

The profile starts one bounded observation window for an active job. Identical
active responses, lifecycle changes within the same job, manual refetches, and
lease-renewal timestamp changes do not reset it. A candidate or job ID change
starts a new window. A manual refresh performs one immediate refetch and starts
a new window only if the response identifies a different applicable job.
Terminal status stops polling permanently.

The stalled UI retains profile actions, uses one polite live region, provides a native manual refresh button, disables it while checking, and renders distinct text for semantic and operational limitations.

Alternative considered: use `application_jobs.updated_at`. Rejected because lease renewal updates that timestamp even when domain work has not advanced.

### Decision 8: OpenSpec artifacts precede main-spec synchronization

All remediation requirements live in this change's delta specs. Until `harden-confirmed-plant-enrichment` is archived, the authoritative remediation requirements live in that active change's delta specifications; archiving synchronizes them into the main OpenSpec specifications. Direct additions currently present in main specs are restored to their prior content after equivalent delta requirements exist, and main specs are never synchronized before archive.

## Risks / Trade-offs

- [Persisted but unindexed evidence is not yet assistant-retrievable] -> Report `partial` with `indexing_deferred` and preserve retry-convergent stable identities.
- [Controlled academic databases may contain ambiguous legacy profiles] -> Leave ambiguous identities null or recreate development data; do not guess by display name.
- [A bounded client polling window can stop before a slow job finishes] -> Preserve manual refresh and all profile actions; backend durability remains authoritative.
- [Basic trusted-domain fetching is not a complete SSRF defense] -> Document the academic boundary and never claim production-grade network isolation.
- [Large dirty worktree makes direct spec restoration risky] -> Restore only remediation additions after delta specs validate; never reset unrelated changes.
- [Generated contracts can drift while backend schemas change] -> Regenerate only after backend contracts and migrations stabilize.

## Migration Plan

1. Create and validate this OpenSpec change and move remediation requirements from direct main-spec edits into delta specs.
2. Apply migration `0013_enrichment_job_progress` before deploying code that writes progress checkpoints.
3. Apply migration `0014_profile_canonical_species_identity`, backfilling only unambiguous controlled data.
4. Deploy backend lifecycle, identity, profile, retrieval, and API changes.
5. Regenerate OpenAPI and deploy frontend candidate handoff and bounded polling.
6. Run focused unit, PostgreSQL/pgvector, migration, frontend, boundary, and OpenSpec verification.
7. Archive and synchronize this change before starting proposal 11.

Rollback uses a compatible prior image or development database recreation. Downgrades of migrations 0013 and 0014 are controlled development/test teardown paths, not routine production rollback: a 0013 downgrade loses durable progress checkpoints and a 0014 downgrade loses canonical profile identity metadata and its uniqueness constraint. Neither downgrade deletes accepted evidence, historical telemetry, or existing profile snapshots.

## Open Questions

No blocking product questions remain. Production-grade HTTP transport, historical profile reconciliation, evidence freshness, explicit rerun, and profile section regeneration are deliberately deferred.
