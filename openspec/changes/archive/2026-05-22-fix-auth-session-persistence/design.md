## Context

The current authentication slice uses Auth.js as the frontend authentication boundary and FastAPI/PostgreSQL as the persisted backend session authority. Successful credential login creates a backend session record and stores the opaque backend session token in server-only Auth.js JWT state. Browser-readable Auth.js session data does not expose that token, and protected frontend route handlers call the backend through a server-side boundary.

The gap is private route authorization. `frontend/src/middleware.ts` currently treats `request.auth` as sufficient for private routes. Because that state is derived from the Auth.js JWT, it can remain present after the backend persisted session is invalidated or expired. The backend will still reject protected API calls, but the frontend private shell can render instead of redirecting to `/login`.

This change should preserve the existing backend persistence model and token non-exposure guarantees while ensuring frontend private access reflects backend session validity.

## Goals / Non-Goals

**Goals:**

- Make backend persisted session validity the effective authority for private frontend access.
- Keep backend session tokens server-only and absent from browser-readable Auth.js session data.
- Ensure expired or invalidated backend sessions redirect private frontend routes to `/login`.
- Ensure protected frontend server route handlers continue to return `401` when no valid backend session exists.
- Preserve logout invalidation of backend session records before clearing frontend Auth.js state.
- Add tests that exercise invalidated/expired backend session behavior at both route guard and route-handler boundaries.

**Non-Goals:**

- No social login implementation.
- No account-management or password-reset completion flow.
- No change to the public backend registration, credential verification, recovery request or Home summary contracts unless needed for session validation.
- No exposure of backend session tokens to client components, browser session payloads or browser-executed API helpers.

## Decisions

### Decision: Backend session validity gates private frontend routes

Private route protection will require a server-side validation step against the backend persisted session authority before allowing access to `/home`, `/identify`, `/search`, `/light-meter`, `/reminders`, `/garden` or `/assistant`.

The validation can use either the HttpOnly backend session cookie or the server-only credential retained by Auth.js. If validation fails, the route guard redirects to `/login` and preserves the callback URL.

Alternative considered: switch Auth.js fully to a database adapter/session table. That would remove the JWT bridge, but introduces adapter mapping and migration risk. The existing backend already owns session records and tests, so validating that existing authority is the smaller, safer change.

Alternative considered: keep middleware unchanged and rely on protected data calls to fail. That still permits stale private shells and does not satisfy the persisted-session boundary.

### Decision: Use a frontend server boundary for validation

The validation logic should live in server-only frontend code shared by middleware or route guards and API route handlers. It must not require client JavaScript to read or forward backend session tokens.

If Next.js middleware runtime constraints prevent direct use of the existing Auth.js token helper or backend fetch flow, private route protection may move to an equivalent server component/layout guard that runs before rendering the private UI. The observable behavior must remain server-side redirection to `/login` before private content renders.

### Decision: Keep backend credential out of browser-visible Auth.js session

Auth.js callbacks may continue retaining the backend credential only in server-only token state, but `session()` must expose only safe identity/auth fields. Tests should continue proving browser-visible session code does not include backend bearer credentials.

### Decision: Logout remains two-phase

Logout should invalidate the backend persisted session through a server-side frontend boundary, then clear Auth.js frontend auth state. If backend invalidation succeeds, subsequent private route access must redirect even if stale Auth.js state is still present.

## Risks / Trade-offs

- Middleware runtime may not support all Node-only Auth.js token or backend helper APIs → use a server component/layout guard if middleware cannot safely validate the backend session.
- Validating backend session on every private navigation adds network latency → keep validation lightweight and limited to private route entry; protected data still uses TanStack Query through route handlers.
- Backend validation during route protection may refresh idle TTL more often → acceptable because private navigation is authenticated activity, but tests should ensure absolute lifetime remains respected.
- Redirect loops are possible if validation runs on auth routes → limit validation to the private route set only.

## Migration Plan

1. Add or reuse a backend session validation path that returns success for valid persisted sessions and `401` for missing, expired or invalidated sessions.
2. Update frontend server-side private route protection to validate against that path before rendering private routes.
3. Keep existing protected route handlers using the same server-only credential resolution path.
4. Add regression tests for valid, missing, expired and invalidated backend session outcomes.
5. Run frontend typecheck/unit tests and backend tests.

Rollback: restore the previous private route guard behavior and keep backend route handlers unchanged. This reintroduces stale private shell risk but does not affect backend API authorization.
