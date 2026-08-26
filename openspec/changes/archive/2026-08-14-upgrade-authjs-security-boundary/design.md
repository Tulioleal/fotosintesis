## Context

The frontend manifest declares `next-auth` with an open beta range and directly declares `@auth/core@^0.37.4`. The lockfile currently resolves vulnerable `next-auth@5.0.0-beta.31`, its transitive `@auth/core@0.41.2`, and the older direct core line. Application code imports `getToken` from `@auth/core/jwt`, even though the installed `next-auth` package exposes `./jwt` as a public export.

Private-route middleware does not use the vulnerable bare `req.auth` pattern. It resolves a server-only backend credential and calls backend `GET /auth/session`; this backend persisted session remains authoritative. The change must retain that stronger boundary and the browser-visible session must continue to exclude `backendCredential`.

Current CI performs a frozen install, lint, typecheck, tests, OpenAPI verification, and build. It neither runs a production dependency advisory scan nor triggers for root manifest and lockfile-only changes. Current focused tests do not arrange missing Auth.js secrets, decode exceptions, callback validation failures, backend validation transport failures, or malformed successful credential-verification payloads.

## Goals / Non-Goals

**Goals:**

- Remove GHSA-8fpg-xm3f-6cx3 from the reproducible dependency graph with the smallest reviewed Auth.js upgrade.
- Converge application imports on the public `next-auth` package and one transitive Auth.js core version.
- Make all authentication configuration, decoding, callback, and validation failure paths deny protected access.
- Preserve credentials login, callback redirects, server-only backend credentials, backend session authority, logout, and private route behavior.
- Make vulnerable Auth.js resolutions and high-severity production dependency advisories fail CI.
- Give a small implementation agent explicit files, behavior, tests, commands, and stopping conditions.

**Non-Goals:**

- Adding providers, changing session lifetime, redesigning auth pages, or changing password/session persistence.
- Replacing Auth.js, backend opaque sessions, middleware route policy, or backend ownership checks.
- Adding authentication rate limiting or password-recovery delivery.
- Refactoring unrelated proxy routes or changing browser-visible session fields.

## Decisions

### Pin the minimal patched Auth.js release

Set `frontend/package.json` to exact `next-auth: "5.0.0-beta.32"`, remove direct `@auth/core`, and regenerate `pnpm-lock.yaml` with the repository's pinned pnpm version. Exact pinning prevents a later beta from entering without review. Beta 32 is the first release outside the proposal's advisory range and minimizes unrelated prerelease migration risk.

Alternatives rejected:

- A caret range remains non-reproducible at manifest resolution time and can admit unreviewed beta behavior.
- A broader latest-version upgrade combines the security fix with avoidable migration work.
- Keeping and aligning a direct `@auth/core` dependency is unnecessary because `next-auth` exports `./jwt`.

### Use only public `next-auth` application imports

Change production and test imports/mocks from `@auth/core/jwt` to `next-auth/jwt`. The currently installed package explicitly exports `./jwt`; the implementation must confirm beta 32 retains that export through typecheck and tests. No application source or test may import `@auth/core` after the change.

### Preserve backend session authority and fail closed at its boundary

`resolveBackendAuthHeaders` remains the only helper that derives server-side backend credentials. It first requires a configured Auth.js secret; a missing secret denies access even if the request carries a backend session cookie. With a configured secret, the existing valid backend-cookie forwarding path remains available before JWT decoding. The helper returns `null` for an invalid auth URL/configuration, token decode exception, missing token, missing concrete `backendCredential`, or malformed token state. `validateBackendSession` returns `false` for credential resolution failure, backend rejection, or backend session validation transport failure. These outcomes cause middleware redirects and protected proxy `401` responses; no thrown Auth.js/configuration object is treated as authentication evidence.

Application-owned failure handling may emit a bounded error category through existing server logging, but it must not log secrets, cookies, JWTs, backend credentials, callback payloads, or decoder exception text. Authentication denial must not depend on log success. This change does not claim control over undocumented third-party Auth.js diagnostics; tests cover responses and diagnostics emitted by application-owned boundary code.

Alternatives rejected:

- Calling `auth()` and checking the returned object's existence reintroduces the advisory's unsafe authorization shape.
- Allowing decode/configuration exceptions to propagate produces protected-route errors rather than conservative denial.
- Trusting a decoded JWT without backend `GET /auth/session` validation would make stale Auth.js state authoritative.

### Validate successful credential responses at runtime

The generated TypeScript response type remains useful for static compatibility but is not runtime validation. Add a Zod schema in `frontend/auth.ts` for the fields consumed from a successful backend response: concrete non-empty user ID, name, valid email, Boolean `email_verified`, non-empty `session_token`, and valid `session_expires_at`. `authorize` returns `null` when JSON parsing or schema validation fails. It must not construct a partially authenticated user or expose response details.

Extract application-owned JWT and session callback logic into testable functions used by the Auth.js configuration. Initial JWT creation requires a concrete user ID, non-empty backend credential, and valid session expiration; malformed callback input throws one generic application-owned authentication error without embedding values. Browser session creation requires a concrete token subject and a backend credential admitted by the credentials-response schema and initial JWT callback before exposing the safe user fields. This callback validation does not call the backend; persisted backend-session authority is checked later at protected server boundaries. Invalid callback state therefore cannot create a browser session or become authorization evidence.

Network failures and backend `5xx` responses continue through Auth.js's authentication error handling. Tests assert denial and sanitized behavior rather than exact internal Auth.js error classes.

### Audit guards without redesigning route policy

Search middleware, route handlers, server helpers, callbacks, and tests for `req.auth`, `request.auth`, bare `auth()` result truthiness, and existence-only session checks. Protected routes continue to use `validateBackendSession`; protected frontend API routes continue to require non-null `resolveBackendAuthHeaders`, with backend ownership checks authoritative. Any discovered existence-only guard is replaced with concrete credential checks and successful persisted backend-session validation as applicable.

The duplicated private route list/matcher architecture is not changed in this security patch; tests retain representative private and public route behavior.

### Use deterministic policy and advisory checks in CI

Add a small Node script and package command that inspect the installed production dependency graph after `pnpm install --frozen-lockfile`. It fails unless all of these are true:

- the manifest pins exactly `next-auth@5.0.0-beta.32`;
- the installed `next-auth` version is exactly `5.0.0-beta.32`;
- the frontend manifest has no direct `@auth/core` dependency;
- exactly one `@auth/core` version is reachable in the production graph;
- no application/test source imports `@auth/core`.

Run that deterministic policy check and `pnpm audit --prod --audit-level high` in frontend CI after frozen installation. Include root `package.json`, `pnpm-lock.yaml`, and `pnpm-workspace.yaml` in frontend workflow path filters. The audit is the advisory scanner; the local policy check specifically prevents recurrence of the affected Auth.js shape even if an advisory service is unavailable outside CI.

Do not add an audit ignore for GHSA-8fpg-xm3f-6cx3. If unrelated high-severity production findings exist, document and remediate them rather than weakening this gate.

### Exercise invalid configuration in a production-server smoke

Add a bounded Node smoke command that starts the already-built Next.js production server on an isolated local port with `AUTH_SECRET` and `NEXTAUTH_SECRET` explicitly removed, waits for readiness, requests a representative private route, and asserts a redirect to `/login` rather than private content or a successful authorization result. The command must always terminate the child server and fail on timeout, unexpected status, or private content. Run it in frontend CI after `pnpm build` and before image publication.

This smoke intentionally verifies fail-closed runtime behavior without weakening the deployed environment's required-secret validation or introducing a public diagnostic endpoint.

## Risks / Trade-offs

- [Beta 32 changes callback or JWT behavior] -> Keep the update minimal and gate it with focused credentials, callback URL, JWT/session, logout, private-route, full frontend, build, and auth E2E tests.
- [Catching decode/configuration errors hides diagnostics] -> Permit only bounded server-side error categories and assert that sensitive values and exception text are absent.
- [The registry advisory service is temporarily unavailable] -> Keep the deterministic local dependency policy check; CI remains red until the production advisory scan succeeds rather than silently skipping it.
- [A broad audit gate exposes an unrelated production advisory] -> Treat it as a real merge blocker or split a reviewed remediation, never suppress the Auth.js advisory.
- [Rollback restores the vulnerable release] -> Never roll back to beta 31. Abort before deployment on regression; after deployment use a previously reviewed non-affected image or a forward fix.

## Migration Plan

1. Add failing focused tests for malformed successful credentials responses and fail-closed server credential/session resolution.
2. Pin beta 32, remove direct core, regenerate the lockfile, and verify the installed dependency graph.
3. Switch imports/mocks to `next-auth/jwt`; add runtime payload validation and fail-closed boundary handling.
4. Complete the existence-guard audit and focused/full authentication regression suites.
5. Add the deterministic dependency policy command, CI advisory scan, and dependency-file path triggers.
6. Run frontend lint, typecheck, full tests, OpenAPI check, production build, invalid-configuration production smoke, authentication E2E, dependency checks, strict OpenSpec validation, and `git diff --check`.
7. Deploy only an immutable image built from the passing lockfile. Rollback must never select beta 31.

## Open Questions

None. Any inability to install exact beta 32 or use its `next-auth/jwt` export is a blocker to report, not permission for the implementation agent to choose a different dependency strategy.
