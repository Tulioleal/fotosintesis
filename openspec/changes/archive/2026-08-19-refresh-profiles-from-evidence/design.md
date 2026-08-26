## Context

Profiles are persisted snapshots generated from accepted evidence. The prior enrichment work added durable background jobs, canonical profile identity, and accepted-evidence persistence, and it deliberately kept profile regeneration out of scope. This change builds on those pieces: after new accepted evidence commits, only the profile sections that depend on changed aspects should become stale and regenerate, without rebuilding unrelated sections or touching garden records and user customizations.

This is an academic project. The design must be coherent, testable, and traceable, but it does not need production-scale backfill, multi-replica guarantees, or automatic evidence expiry.

## Goals / Non-Goals

**Goals:**

- Persist a deterministic evidence fingerprint and generation policy version per profile section.
- Map sections to canonical aspects so evidence changes affect only the sections that depend on them.
- Regenerate stale sections through durable, retryable, idempotent background jobs.
- Replace stale sections atomically while keeping the previous version readable on failure.
- Reconcile legacy profiles without fingerprints without deleting historical text.
- Expose per-section freshness and refresh status without blocking profile reads.
- Invalidate frontend profile queries after a committed section replacement.

**Non-Goals:**

- A persistent longitudinal care plan.
- Rewriting user notes, locations, images, or reminders.
- Automatic deletion of historical evidence or profile versions.
- Making profile generation synchronous with confirmation.
- Time-based evidence expiration or source supersession.

## Decisions

### Decision 1: Per-section fingerprint, not whole-profile fingerprint

Each profile section has a stable identifier and an applicable aspect set. Each generated version records the deterministic evidence fingerprint and generation policy version that produced it. The fingerprint is derived from accepted evidence identifiers and versions for the section's aspects, not from retrieval order or model response formatting.

Alternative considered: a single whole-profile fingerprint. Rejected because any evidence change would invalidate every section and force a full rebuild.

### Decision 2: Aspect-to-section mapping drives staleness

Sections map to canonical aspects. When accepted evidence changes, the system computes the affected aspects and marks only the sections mapped to those aspects stale. A generation policy version covers future mapping changes.

Alternative considered: comparing section text directly. Rejected because text diffs do not capture whether new evidence is semantically relevant to a section.

### Decision 3: Durable refresh jobs collapse work by fingerprint

New evidence updates the knowledge store and vector index transactionally, then a durable refresh job is scheduled for the affected sections of one species. Jobs are keyed so concurrent acquisitions that change the same evidence collapse into one refresh rather than repeated rebuilds. Generation reads the latest accepted evidence when the job runs.

Alternative considered: regenerating inline during evidence ingestion. Rejected because it would block confirmation and couple ingestion to generation.

### Decision 4: Atomic replacement with a readable fallback

A successful regenerated section replaces the prior active version atomically. A failed section keeps the prior visible version and is surfaced as stale with an explicit limitation, so a failed refresh never erases the last usable content.

Alternative considered: deleting stale sections before regeneration. Rejected because a crash or failure would leave no readable content.

### Decision 5: Legacy profiles are reconciled, not assumed valid

Profiles without fingerprints are treated as unknown, not automatically current. A bounded reconciliation pass evaluates their sections against current evidence coverage and prioritizes sections that contain insufficient-evidence fallback text. Existing sourced sections stay visible until a replacement succeeds.

Alternative considered: rewriting all legacy sections on migration. Rejected because it would create churn and could regress quality without new evidence.

## Risks / Trade-offs

- [Aspect-to-section mapping may evolve] -> Store a generation policy version and record it per section version.
- [Concurrent acquisition may trigger repeated refresh] -> Collapse refresh work by fingerprint and stable job keys.
- [New model output may regress quality] -> Keep the prior version until the replacement commits.
- [Reconciliation may create load] -> Process legacy profiles in bounded durable batches.
- [Users may mistake stale data for current] -> Expose per-section freshness and refresh status.

## Migration Plan

1. Add the section-version / evidence-fingerprint persistence migration, leaving existing sections without fingerprints.
2. Add refresh job payloads and handlers; wire evidence-change signals after accepted ingestion.
3. Update profile response schemas and generated OpenAPI contracts with freshness and refresh metadata.
4. Update frontend views and TanStack Query invalidation for committed replacements.
5. Run the bounded legacy reconciliation pass.
6. Verify with focused tests covering partial refresh, failure, concurrency, legacy data, and cache updates.

Rollback uses a prior compatible image. A downgrade of the fingerprint migration drops section-version metadata but does not delete profile text, evidence, or garden records.

## Open Questions

No blocking product questions remain. Time-based evidence expiry, source supersession, and historical backfill are deliberately deferred.
