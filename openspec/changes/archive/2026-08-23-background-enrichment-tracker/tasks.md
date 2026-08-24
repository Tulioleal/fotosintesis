## 1. Backend Activity Contract

- [x] 1.1 Define sanitized owner-scoped enrichment activity schemas for active and retained terminal jobs.
- [x] 1.2 Add repository queries that join owner associations, candidate/profile context, and bounded job results without exposing raw payloads or evidence.
- [x] 1.3 Add an authenticated activity endpoint with retention, ordering, pagination/cap, and not-found/authorization tests.
- [x] 1.4 Include related `refresh_profile` activity and explicit phase metadata when profile refresh follows evidence enrichment.

## 2. Frontend Activity Observer

- [x] 2.1 Add the generated API contract and client method for owner-scoped enrichment activity.
- [x] 2.2 Add an app-shell React Query observer that polls only while active work exists and caches activity for Home, Garden, and navigation consumers.
- [x] 2.3 Add session-scoped terminal outcome deduplication and accessible complete, partial, and failed announcements.
- [x] 2.4 Preserve profile-local polling and reconcile activity transitions without duplicate requests or focus movement.

## 3. Home And Garden Experience

- [x] 3.1 Add a compact active-work indicator to Home with plant context, background-processing explanation, and authorized profile link.
- [x] 3.2 Add active and retained terminal enrichment status to Garden list/detail surfaces without blocking existing actions.
- [x] 3.3 Add distinct copy for evidence-ready versus profile-refreshing states and sanitized recovery guidance for failures.
- [x] 3.4 Add loading, empty, stale, error, partial, and terminal UI states with accessible status semantics.

## 4. Verification And Documentation

- [x] 4.1 Add backend tests for owner isolation, retention, bounded response shape, phase distinction, and terminal outcomes.
- [x] 4.2 Add frontend unit tests for shared polling, cache reuse, notification deduplication, and Home/Garden rendering.
- [x] 4.3 Add Playwright coverage for navigating away from a profile while enrichment runs and observing terminal activity later.
- [x] 4.4 Regenerate OpenAPI TypeScript types, run focused/full frontend and backend suites, and document rollout/rollback behavior.
## 5. Verification Remediation

- [x] 5.1 Scope activity cache and session deduplication by authenticated user.
- [x] 5.2 Reconcile terminal refreshes once per exact profile query.
- [x] 5.3 Bound activity summary rendering and preserve overflow metadata.
- [x] 5.4 Enforce phase, status, job-type, and result consistency.
- [x] 5.5 Harden authenticated response caching and proxy errors.
- [x] 5.6 Make tracker E2E interception deterministic and contract-valid.
- [x] 5.7 Complete confirmation, stale-state, deployment, and Home contract tests.
- [x] 5.8 Bound retention and session-storage configuration.
- [x] 5.9 Reconcile tracker documentation and run full verification.

## 6. Round 2 Verification Remediation

- [x] 6.1 Reset announcer state on authenticated identity change.
- [x] 6.2 Scope profile/enrichment caches by user.
- [x] 6.3 Surface active-only overflow count.
- [x] 6.4 Reconcile rollback documentation with forward-recovery policy.
- [x] 6.5 Handle proxy fetch rejection with sanitized 502.
- [x] 6.6 Make E2E stale-data journey preserve cache (no reload).
- [x] 6.7 Use real accepted names in all E2E activity fixtures.
- [x] 6.8 Add lifecycle/timestamp contract validation and remaining hardening.
- [x] 6.9 Run full verification and update archive gate.
