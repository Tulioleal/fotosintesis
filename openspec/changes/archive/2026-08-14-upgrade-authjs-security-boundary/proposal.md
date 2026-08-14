## Why

The reproducible frontend lockfile resolves `next-auth@5.0.0-beta.31`, which is affected by GHSA-8fpg-xm3f-6cx3, while a direct `@auth/core` dependency creates a second incompatible authentication-core line. The current backend-session validation reduces exposure, but the known-vulnerable dependency, unaligned JWT decoder, and absence of a dependency security gate must be corrected before unrelated feature work continues.

## What Changes

- Pin `next-auth` to a reviewed release at or above `5.0.0-beta.32` that is outside the advisory range, and commit the reproducible lockfile result.
- Replace the direct `@auth/core/jwt` application import with the supported `next-auth` JWT export and remove the direct `@auth/core` dependency so one Auth.js core line remains.
- Make missing secrets, invalid Auth.js configuration, malformed credentials responses, JWT decode failures, and callback failures deny authentication without exposing secrets or credentials.
- Audit every middleware, route handler, server helper, and callback so protected behavior requires concrete identity plus authoritative backend-session validation rather than a truthy Auth.js object.
- Preserve credentials login, callback URLs, browser credential non-exposure, backend-session forwarding, logout, and private-route redirects.
- Add focused authentication regressions, lockfile policy checks, production dependency scanning, and CI path coverage for root dependency files.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `authentication-home`: Require a patched and intentionally pinned Auth.js dependency set while preserving the existing credentials flow.
- `secure-auth-session-boundary`: Require Auth.js configuration, callback, and token-decoding failures to fail closed without exposing backend credentials.
- `auth-cookie-bridge`: Resolve login-created backend credentials through the aligned public `next-auth` JWT API and reject malformed or undecodable state.
- `testing-deployment`: Enforce reproducible authentication lockfile policy and production dependency advisory scanning in frontend CI.

## Impact

- Frontend dependencies and lockfile: `frontend/package.json`, `pnpm-lock.yaml`.
- Authentication configuration and server boundary: `frontend/auth.ts`, `frontend/src/lib/server/backend-session.ts`, middleware, auth route handlers, and their tests.
- CI and deployment verification: `.github/workflows/frontend-ci.yml` and focused authentication smoke coverage.
- No backend API, database schema, browser-visible session shape, or resource-ownership contract is intentionally changed.
