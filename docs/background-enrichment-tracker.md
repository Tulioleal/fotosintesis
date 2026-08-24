# Background Enrichment Tracker

The authenticated cross-page tracker surfaces durable confirmed-plant
enrichment work that keeps running after the user leaves the profile. It is
defined by the `background-enrichment-tracker` change in
`openspec/changes/background-enrichment-tracker/`.

## What It Does

- **Owner-scoped activity endpoint** — `GET /jobs/enrichment-activity` returns
  the requesting user's active (pending/processing) and recently terminal
  (complete/partial/failed) enrichment jobs within a bounded retention window,
  newest first, capped by `ENRICHMENT_ACTIVITY_MAX_ITEMS` (default 20).
- **Cursor pagination with stable ordering** — responses carry
  `has_more` plus an opaque `next_cursor` over the keyset tuple
  `(updated_at DESC, id DESC)`. Each phase query fetches at most
  `limit + 1` rows and applies the cursor condition in SQL, so database work is
  bounded before serialization. Malformed cursors return HTTP 422; tied
  timestamps break by exact job id descending. For an unchanged activity
  dataset, following `next_cursor` returns every visible item exactly once;
  items updated during a traversal may move into a subsequent fresh traversal.
  The frontend observer walks all pages itself, so hidden active work on later
  pages keeps polling alive.
- **Metadata-only privacy boundary** — each item exposes job id, kind, phase
  (`evidence` vs `profile_refresh`), lifecycle, timestamps, display context,
  bounded result counts, limitation categories, and sanitized error category.
  Raw payloads, evidence, quotes, claims, leases, and worker ownership data are
  never returned. Oversized or corrupt persisted result JSON is clamped to
  schema bounds instead of failing response validation.
- **Causal refresh association** — when an enrichment run accepts evidence it
  enqueues its profile refresh in the same transaction and records a durable
  many-to-many link in `profile_refresh_enrichment_jobs` (migration
  `0020_refresh_enrichment_assoc`). Refresh activity is surfaced only through
  this causal chain; payload species matching is never used for authorization,
  and historical unassociated refreshes stay hidden. Legacy reconciliation
  creates no association.
- **Authorized candidate context on every visible activity** — both phases
  select one deterministic owner candidate per job (window-function rank over
  the association chain) and revalidate candidate/image ownership at read time
  with the same predicate as the direct status query. Refresh items therefore
  carry a real `candidate_id` and the candidate's accepted scientific name, so
  every actionable activity link points at a valid profile route.
- **Evidence vs profile-refresh phases** — `enrich_confirmed_plant` jobs are
  `evidence`; causally related `refresh_profile` jobs surface as
  `profile_refresh`. The UI never claims profile sections are updated from
  evidence completion alone.
- **Exactly one app-shell observer** — `EnrichmentActivityProvider` mounts once
  inside `AppShell` and owns the single React Query polling observer. The
  announcer, Home, Garden list/detail, and the profile consume the same context;
  nothing else calls the activity endpoint. Polling runs only while active work
  exists and stops at terminal states.
- **Confirmation wakes the tracker** — after a successful identification or
  manual-search confirmation seeds the candidate-detail cache, the flow
  invalidates the activity query before navigating to the profile, so a stopped
  tracker immediately reflects the new work. Failed confirmations invalidate
  nothing. The confirmation response itself never fabricates an activity item.
- **Session-scoped terminal notification queue** — unseen terminal outcomes are
  enqueued newest-first (id tie-breaking), displayed one at a time, and advanced
  on dismissal. Only displayed versions persist to session storage, so every
  unseen outcome can eventually be announced while announced ones never repeat.
  Refresh failures use refresh-specific recovery guidance.
- **Profile reconciliation** — `PlantProfileView` keeps its local candidate
  polling and additionally watches related refresh activity through the shared
  provider context. When a related refresh reaches a terminal state the exact
  profile query (candidate + accepted name + language, per user) is
  invalidated once; identical rerenders, remounts, and other consumers never
  repeat it.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS` | `24` | How long terminal jobs remain visible. |
| `ENRICHMENT_ACTIVITY_MAX_ITEMS` | `20` | Cap on items returned per response (also overrides `limit=100`). |

## Rollout

1. Deploy the backend: migration `0020_refresh_enrichment_assoc` adds the
   durable refresh–enrichment association table (composite primary key,
   cascading foreign keys, enrichment-side index). No backfill is required.
2. Regenerate the OpenAPI contract (`openapi-baseline.json`) and the frontend
   TypeScript client (`pnpm openapi:generate`); `pnpm openapi:check` must pass.
   The endpoint gains the `cursor` query parameter and `next_cursor` field.
3. Deploy the frontend: the app-shell provider, announcer queue, Home/Garden
   summaries, and paginated client method land behind the existing
   authenticated routes. Candidate-local profile polling is unchanged.
4. Observe traffic to `/jobs/enrichment-activity`; it stays empty until users
   confirm candidates, then only returns jobs authorized through owned
   candidates and causal associations.

## Rollback

Roll back in this order:

1. **Stop or drain workers that write refresh associations.** A running
   worker executing the new producer code inserts into
   `profile_refresh_enrichment_jobs`; dropping the table underneath it breaks
   every enrichment completion.
2. Roll back the backend and worker producer code (the enrichment service and
   signal enqueue).
3. Remove the frontend observer (`EnrichmentActivityProvider` mount in
   `AppShell.tsx`) and its consumers.
4. Recover forward with a compatible image or a forward-fix migration. Keep
   migration `0020_refresh_enrichment_assoc` in place: durable refresh
   associations, queued jobs, and evidence must never be discarded, and
   `alembic downgrade` is not part of this feature's rollback path.

> Do not drop `profile_refresh_enrichment_jobs` while workers running the new
> producer code are active.

The confirmation flow that schedules enrichment keeps working whether or not
the tracker is deployed.

## E2E

`scripts/run-enrichment-e2e.sh` runs a direct `docker build` tagged
`photosynthesis-backend-e2e` before starting Compose services; dependency
installation happens during image build, and E2E containers run migrations plus
uvicorn without `--reload`.

Activity HTTP responses in the tracker Playwright tests are browser-route
fixtures (`page.route` on `/api/jobs/enrichment-activity*`): they exercise the
frontend observer, pagination walker, queue, and link behavior. Backend
authorization, refresh causality, cursor validation, and SQL-level pagination
are covered by PostgreSQL integration tests, not by these E2E journeys. The
pagination walker itself is covered by frontend unit tests plus the two-page
Playwright journey; SQL keyset pagination is covered by PostgreSQL integration
tests.

## Session Storage And Bounds

- Announced terminal outcomes and refresh-reconciliation claims live in
  per-user `sessionStorage` keys (`...:v2:${userId}`); at most the newest
  `MAX_STORED_OUTCOME_VERSIONS = 200` versions are kept per user.
- The React Query cache is keyed by authenticated user id
  (`activityQueryKey(userId)`), logout drops activity queries before
  `signOut`, and no activity request is issued before the identity exists.
- Responses are `Cache-Control: private, no-store` end to end; proxy error
  bodies are replaced by bounded app-owned detail strings.
- Rendering is bounded to five active and five recent rows with an overflow
  count; aggregation still walks every page.

## Query Plan Review

`EXPLAIN (ANALYZE, BUFFERS)` for both activity phases (evidence via candidate
associations, refresh via causal associations) was measured against
PostgreSQL: both plans run in well under 0.1 ms at current scale using the
existing indexes (`ix_candidate_enrichment_jobs_job_id`,
`ix_candidate_enrichment_jobs_owner_candidate_policy`,
`pk_profile_refresh_enrichment_jobs`,
`ix_profile_refresh_enrichment_jobs_enrichment_id`,
`ix_application_jobs_user_id`). No additional index is justified now.
Reproduce the measured plans with
`psql "$DATABASE_URL" -f scripts/db/activity_query_plan.sql`.
Revisit only if `application_jobs` grows past ~10^6 rows and `pg_stat_statements`
shows the activity queries dominating latency; then evaluate
`(job_type, status, updated_at DESC, id DESC)` with measured plans.

Association role integrity is enforced at write time by the repository and
revalidated at read time; a DB-level trigger is deliberately deferred until
direct-SQL writers exist.

## Verification

- Backend: `tests/test_enrichment_activity_repository.py` (SQLite) covers
  owner isolation, retention, deduplication, causal associations, cursor
  ordering bounds, and sanitization; `tests/integration/test_enrichment_activity_api.py`
  (PostgreSQL, per-test schemas) covers the HTTP boundary, pagination walks,
  malformed cursors, foreign-context leaks, and outcome serialization.
  `tests/integration/test_profile_refresh.py` covers association durability,
  fingerprint reuse, legacy non-association, and transactional rollback.
- Frontend: `src/lib/enrichment-activity.test.ts` covers links, copy phases,
  and polling; `EnrichmentActivitySummary.test.tsx`,
  `EnrichmentActivityAnnouncer.test.tsx` (queue semantics),
  `AppShell.test.tsx` (single observer + interval), `IdentifyFlow.test.tsx` /
  `SearchFlow.test.tsx` (confirmation invalidation), `PlantProfileView.test.tsx`
  (refresh reconciliation), and `GardenList` / `GardenDetail` tests cover the
  remaining behaviors; `e2e/enrichment-journeys.spec.ts` covers the journeys
  listed above.
