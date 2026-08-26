## Context

Confirmation already creates an owner-authorized durable enrichment job, and the profile page polls that job while it is mounted. The confirmation response contains enough metadata to identify the job, but Home and Garden do not expose it and navigation away from the profile ends the user's visibility. The change spans the job repository/API, response contracts, the authenticated app shell, and React Query cache behavior.

## Goals / Non-Goals

**Goals:**

- Provide an owner-scoped, bounded activity feed for active and recently terminal enrichment work.
- Make active work discoverable from Home and Garden and link each item to its profile.
- Keep status safe, metadata-only, and consistent with existing job lifecycle states.
- Announce terminal transitions once per job and user session, including partial and failed outcomes.
- Represent profile refresh separately when it is scheduled after evidence enrichment.

**Non-Goals:**

- Changing enrichment policy, provider selection, evidence judging, taxonomy validation, or retry behavior.
- Exposing raw prompts, payloads, source bodies, claims, quotes, or provider diagnostics.
- Building browser push notifications or requiring a new external notification service.
- Inferring botanical meaning or language through client-side keyword heuristics.

## Decisions

1. **Add an owner-scoped activity endpoint rather than relying on browser storage.**
   The backend will return a bounded list of jobs associated with the authenticated user, filtered to active work and a short terminal-retention window. This survives reloads and device changes and preserves authorization. A local-only job ID tracker was rejected because it becomes stale, does not work across devices, and cannot safely represent shared jobs.

2. **Return a normalized activity view, not raw job rows.**
   The API will expose job ID, job kind, lifecycle, timestamps, scientific display context, candidate/profile link context, bounded result counts, limitations, and sanitized error category. Payloads, evidence, ownership internals, and lease data remain excluded. This keeps the activity contract stable while preserving the existing metadata-only privacy boundary.

3. **Use one app-shell React Query observer with route-local rendering.**
   A provider-level observer will poll while active work exists and cache the activity list. Home, Garden, and a compact navigation indicator can consume the same cache without independent polling waterfalls. The profile query remains authoritative for detailed candidate status.

4. **Use session-scoped terminal deduplication for notifications.**
   The client will record observed terminal job IDs and outcome versions in memory or versioned session storage. It will announce a terminal result once per session, while the activity list remains visible on every load. Persistent server-side notification records are deferred until product requirements justify read/unread history.

5. **Model evidence and profile refresh as related activities.**
   The activity contract will distinguish `enrich_confirmed_plant` from `refresh_profile`. Evidence completion may therefore display “evidence ready” while profile refresh remains active. The UI will not claim that profile sections are updated until the refresh activity is terminal.

## Risks / Trade-offs

- **[Polling overhead]** A global observer adds requests while jobs are active → use a bounded interval, stop when no active jobs exist, and cap returned rows.
- **[Shared-job visibility]** Multiple owners may observe one shared job → filter associations by the requesting owner and never expose other candidates.
- **[Terminal noise]** Partial or failed jobs could create repeated notices → deduplicate by job ID and terminal outcome version.
- **[Stale profile link]** A profile may be deleted or no longer available → every surfaced item carries an authorized candidate id, so links always target a valid profile route; items without valid candidate context are filtered out server-side.
- **[Phase ambiguity]** Evidence and profile refresh can finish at different times → expose separate job kinds and explicit copy for each phase.

## Migration Plan

1. Add the normalized authenticated activity schema and endpoint without changing existing confirmation or profile endpoints.
2. Add repository queries and indexes if needed for owner-scoped active/recent jobs.
3. Add the app-shell observer and Home/Garden rendering behind existing authenticated routes.
4. Regenerate and validate the OpenAPI TypeScript client.
5. Roll back by removing the observer and rendering while leaving durable jobs and existing profile polling intact; the new read endpoint can remain backward-compatible.

## Resolved Decisions

- Terminal activity remains visible for 24 hours by default, configurable via `ENRICHMENT_ACTIVITY_TERMINAL_RETENTION_HOURS`.
- Failed enrichment exposes no new retry endpoint: the activity item links to the profile, where existing recovery UI applies.
- The global indicator lives in Home/Garden/profile summaries plus the shell announcer; navigation chrome is unchanged.
