## Context

The secure auth session boundary change removed browser-visible backend bearer token usage and added frontend route handlers for protected Home and logout calls. Those handlers forward the incoming `fotosintesis_session` cookie to the backend, but the current Auth.js credential login calls backend `/auth/credentials/verify` from the frontend server and only reads the JSON response. A backend `Set-Cookie` header produced during that server-side fetch is not automatically written to the browser response, so the browser may never receive the backend HttpOnly session cookie needed by the route handlers.

## Goals / Non-Goals

**Goals:**

- Ensure successful credential login establishes a browser HttpOnly backend session cookie that frontend route handlers can forward.
- Keep backend session credentials out of browser-readable Auth.js session data and client components.
- Preserve existing backend authentication endpoints and response contracts.
- Add tests for the login-to-Home route-handler path, not only manual cookie forwarding.

**Non-Goals:**

- No new login UI, auth provider, social login flow or password reset behavior.
- No reintroduction of client-side `Authorization: Bearer <backend session token>` calls.
- No backend database or session schema changes.
- No replacement of Auth.js as the frontend authentication boundary.

## Decisions

- Store the backend session token only in server-side Auth.js JWT state, not in the browser-visible session payload.
  - Rationale: Auth.js route handlers can access JWT state server-side while `session()` can continue returning only safe identity fields.
  - Alternative considered: copy the backend `Set-Cookie` from the credential fetch into the Auth.js response. Rejected as the primary approach because Auth.js credentials callbacks do not provide a simple response mutation boundary and cookie attribute mismatches can be fragile across environments.

- Update frontend protected route handlers to derive the backend credential server-side before falling back to incoming cookie forwarding.
  - Rationale: this preserves the current route-handler pattern and makes protected calls work immediately after Auth.js login even when no backend cookie is present on the browser request.
  - Alternative considered: have client components call a login bridge endpoint before Auth.js sign-in. Rejected because it complicates login ordering and increases surface area.

- Keep browser-readable session output free of token-like fields.
  - Rationale: `useSession()` remains accessible to client JavaScript and must not expose backend credentials.
  - Alternative considered: expose a short-lived proxy token. Rejected as unnecessary for the current route-handler architecture.

- Add tests that exercise route-handler credential resolution from Auth.js server state and assert no bearer credential appears in client session data.
  - Rationale: previous tests only proved behavior when a cookie was manually supplied; the regression needs to cover the post-login path.

## Risks / Trade-offs

- Auth.js JWT field naming could accidentally leak through future `session()` changes -> keep a regression test that inspects browser-visible session shaping and client code.
- Server route handlers become coupled to Auth.js server helpers -> keep credential extraction small and local to protected boundary handlers until more endpoints need it.
- Existing cookie forwarding remains useful for compatibility but may hide missing JWT state in tests -> cover both JWT-derived and cookie-forwarding paths.

## Migration Plan

- Add server-only backend credential retention in Auth.js JWT callback.
- Update Home and logout route handlers to build backend request credentials from server-only Auth.js state or existing HttpOnly cookie state.
- Add tests for login-created server credential use, unauthorized handling and absence of browser-visible backend tokens.
- Run frontend typecheck and tests.
