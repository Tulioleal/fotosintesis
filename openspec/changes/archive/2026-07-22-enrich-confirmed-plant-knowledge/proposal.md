## Why

Confirming a taxonomically validated identification currently records the selection but does not check or improve local species evidence. On an empty or sparsely populated installation, users can therefore reach a profile dominated by insufficient-evidence text even though the application already has trusted acquisition, semantic judging, vector indexing, and durable background-job infrastructure.

## What Changes

- Schedule durable species enrichment only when a user confirms a taxonomically validated candidate, within the same successful workflow boundary as confirmation; if durable scheduling is unavailable, confirmation does not succeed.
- Identify the species by accepted GBIF key plus normalized binomial when both are available, using a taxonomy-validated normalized binomial as fallback when the key is absent; reject unvalidated free-form identities.
- Evaluate local evidence coverage against the structured registry of required profile aspects, using semantic judging rather than document counts or deterministic text matching.
- Acquire trusted evidence only for aspects judged missing, while retaining the existing source validation, answerability thresholds, and stricter safety-sensitive rules.
- Persist, embed, and index only accepted source-supported evidence with explicit content, individual aspect-support, validation-run, source, date, confidence, review status, and provenance metadata.
- Deduplicate only active enrichment by canonical species identity and enrichment policy version; give every terminal-capable run its own permanent idempotency identity and deduplicate evidence independently of enrichment policy or complete aspect sets.
- Expose `pending`, `processing`, `complete`, `partial`, and `failed` enrichment state while keeping the latest persisted profile snapshot navigable throughout processing and failure.
- Record bounded metrics for avoided acquisition, completion time, and partial outcomes.

## Capabilities

### New Capaenrich-confirmed-plant-knowledgebilities

- `confirmed-plant-enrichment`: Durable enrichment lifecycle, composite canonical species identity, active-only work sharing, semantic evidence coverage, targeted acquisition, idempotent persistence, and bounded outcomes following confirmation.

### Modified Capabilities

- `plant-identification-taxonomy`: Successful confirmation of a validated candidate durably schedules enrichment; unconfirmed or invalid candidates do not.
- `knowledge-rag-acquisition`: Existing retrieval, trusted acquisition, semantic judging, validated persistence, embedding, and indexing paths support offline acquisition targeted to missing canonical profile aspects.
- `plant-profile-garden`: The latest persisted profile snapshot remains available and exposes enrichment status and limitations while current indexed evidence remains available separately to assistant retrieval.

## Impact

- Extends confirmation orchestration, response contracts or related status resources, and generated OpenAPI TypeScript clients.
- Adds a versioned enrichment job payload, policy-versioned candidate associations, registered worker handler, active-work deduplication, per-run idempotency, bounded result/error contracts, and coverage queries built on `durable-background-jobs`.
- Extends knowledge provenance and uniqueness metadata with content-level evidence identity, idempotent individual-aspect associations, validation runs, source retrieval/publication dates, source versions, and content hashes.
- Updates profile API/query behavior and TanStack Query polling or invalidation so pending work never blocks navigation.
- Adds backend, worker, API, frontend, and integration tests for empty, covered, partial, failed, retried, and duplicate scenarios.
