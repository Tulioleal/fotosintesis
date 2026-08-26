## Why

Confirmed-plant enrichment is substantially implemented, but verification found correctness and traceability gaps around durable partial progress, canonical species identity, profile evidence selection, frontend observation, and the OpenSpec workflow. These gaps must be closed before profile refresh work begins so proposal 02 has a coherent, testable academic implementation and proposal 11 remains an independent later change.

## What Changes

- Make durable accepted progress, rather than semantic judge output alone, determine whether exhausted enrichment is `partial` or `failed`.
- Serialize progress checkpoint merges and preserve accepted progress across live failure and crash reconciliation.
- Balance local enrichment retrieval across requested canonical aspects before semantic judging.
- Carry the server-authorized canonical species identity from confirmed candidate context through profile metadata and later assistant retrieval.
- Restrict newly created profile snapshots to accepted evidence while leaving every existing persisted snapshot unchanged.
- Keep confirmed-plant persistence limited to successfully fetched trusted content with bounded academic-project HTTP safeguards.
- Bound frontend enrichment polling with an accessible manual status refresh and explicit operational limitations.
- Add requirement-to-test traceability and a real regression proving enrichment does not trigger profile regeneration.
- Organize this remediation as an active OpenSpec change instead of editing main specifications directly.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `confirmed-plant-enrichment`: Define durable accepted-progress outcomes, balanced local retrieval, fetched-only persistence, reconfirmation semantics, and later canonical assistant retrieval.
- `durable-background-jobs`: Define failure-derived enrichment partials and checkpoint-based terminal decisions.
- `assistant-agent`: Preserve server-resolved confirmed-candidate identity through assistant context and retrieval.
- `knowledge-rag-acquisition`: Define bounded trusted fetching and deterministic source identity appropriate to the academic project.
- `plant-profile-garden`: Expose canonical profile metadata, use accepted evidence for new snapshots, bound polling, and preserve existing snapshots without regeneration.

## Impact

- Adds enrichment-progress and canonical-profile-identity migrations.
- Updates enrichment persistence, job finalization, retrieval, profile creation, assistant context, and profile status UI.
- Extends profile and assistant API contracts and generated TypeScript types.
- Adds focused backend, PostgreSQL/pgvector, frontend, migration, and boundary tests.
- Does not regenerate, invalidate, replace, version, or refresh persisted profile sections and does not schedule profile-refresh work. Those behaviors remain exclusively within `refresh-profiles-from-evidence`.
- Does not require production-grade DNS pinning, peer-IP verification, historical production-data repair, evidence expiration, source supersession, or an explicit failed-job rerun endpoint.
