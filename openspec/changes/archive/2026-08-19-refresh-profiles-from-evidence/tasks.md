## 1. Section Fingerprints and Persistence

- [x] 1.1 Add the section-version / evidence-fingerprint migration, leaving existing sections without fingerprints.
- [x] 1.2 Implement deterministic evidence fingerprint computation from accepted evidence identifiers and versions per aspect set.
- [x] 1.3 Store stable section identifiers, applicable aspects, generation policy version, provenance, confidence, limitations, and generation timestamps per section version.

## 2. Staleness and Refresh Jobs

- [x] 2.1 Map profile sections to canonical aspects and compute affected sections from changed aspects.
- [x] 2.2 Mark only affected sections stale when evidence changes.
- [x] 2.3 Add durable, idempotent profile refresh job payloads and handlers that regenerate stale sections from the latest accepted evidence.
- [x] 2.4 Collapse concurrent refresh work by fingerprint so repeated signals do not duplicate active versions.
- [x] 2.5 Replace stale sections atomically on success and keep the previous version readable and marked stale on failure.

## 3. Evidence-Change Signals and Reconciliation

- [x] 3.1 Emit evidence-change signals transactionally after accepted ingestion with species identity and changed aspects.
- [x] 3.2 Add a bounded legacy reconciliation pass that evaluates fingerprint-less profiles and prioritizes insufficient-evidence fallback sections.

## 4. API and Frontend

- [x] 4.1 Add per-section freshness and refresh status to profile response schemas.
- [x] 4.2 Regenerate OpenAPI contracts and generated TypeScript types.
- [x] 4.3 Invalidate TanStack Query profile caches after a committed section replacement and communicate refresh state without blocking reads.

## 5. Tests and Verification

- [x] 5.1 Add tests for partial refresh, failure fallback, concurrency convergence, legacy reconciliation, and cache invalidation.
- [x] 5.2 Run backend lint and focused profile, job, migration, and reconciliation tests.
- [x] 5.3 Run frontend lint, typecheck, and focused profile query tests.
- [x] 5.4 Run `openspec validate "refresh-profiles-from-evidence" --strict`.
