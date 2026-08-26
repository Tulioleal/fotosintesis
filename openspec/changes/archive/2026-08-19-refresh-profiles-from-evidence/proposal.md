## Why

Plant profiles currently behave as immutable snapshots after first creation, so newly accepted evidence does not improve an existing profile. Rebuilding whole profiles would create unnecessary churn. The system needs section-level staleness and regeneration so only affected sections refresh when validated evidence changes.

## What Changes

- Record the evidence fingerprint used to generate each profile section.
- Associate profile sections with canonical aspects and a generation policy version.
- Detect which sections are affected when validated evidence changes and mark only those stale.
- Schedule durable, idempotent section-level regeneration jobs.
- Replace stale sections atomically after their regenerated version persists safely, preserving unaffected sections.
- Retain provenance, confidence, limitations, and generation timestamps per section.
- Reconcile profiles created before evidence fingerprints existed.
- Expose profile freshness and refresh status to API consumers.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `plant-profile-garden`: Version and refresh profile sections from evidence.
- `knowledge-rag-acquisition`: Emit evidence-change signals after accepted ingestion.
- `garden-query-data-fetching`: Refresh cached profile data after a committed section replacement.

## Impact

- Add section-version or equivalent evidence-fingerprint persistence.
- Add profile refresh job payloads, handlers, and reconciliation commands.
- Update profile response schemas with freshness and refresh metadata.
- Update frontend profile views to communicate refresh without blocking reads.
- Update generated OpenAPI contracts and TanStack Query invalidation behavior.
- Add metrics for stale sections, refresh latency, failures, and replacements.
