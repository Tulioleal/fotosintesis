## Context

The frontend currently obtains a backend session token during Auth.js credential authorization, stores that token in the Auth.js JWT callback and exposes it through the browser-readable session returned by `useSession()`. Client components then call protected backend endpoints with `Authorization: Bearer <backendSessionToken>`.

The intended boundary is stricter: backend session tokens are opaque server-side credentials and should remain in HttpOnly cookies or other server-only state. Browser code can know whether the user is authenticated, but it must not receive or forward the backend session token directly.

## Goals / Non-Goals

**Goals:**

- Remove `backendSessionToken` from browser-readable Auth.js session data.
- Stop client components from sending backend session tokens in `Authorization` headers.
- Add a server-side frontend boundary for protected backend business calls such as Home summary.
- Keep Home loading, retry and error behavior intact.
- Keep Auth.js login, logout and route protection behavior intact.
- Add tests that prevent reintroducing client-visible backend session tokens.

**Non-Goals:**

- No new authentication provider or social login implementation.
- No redesign of the auth screens or Home UI.
- No change to backend protected endpoint contracts unless a small cookie-forwarding adjustment is required.
- No database persistence work; that is covered by the separate `persist-auth-sessions` change.

## Decisions

- Introduce frontend server-side route handlers for protected backend business endpoints.
  - Rationale: route handlers can read HttpOnly cookies from the incoming request and call the backend without exposing the token to browser JavaScript.
  - Alternative considered: move Home to a server component and fetch backend data directly there. Rejected for this slice because Home already uses TanStack Query for loading, retry and recoverable error states.

- Keep Auth.js session data limited to safe user-facing fields.
  - Rationale: `useSession()` is browser-readable; it should expose identity and auth status, not backend credentials.
  - Alternative considered: encrypt the backend token inside the Auth.js JWT and keep mapping it into session data. Rejected because mapping it into session data still exposes it to the browser.

- Prefer cookie forwarding from route handlers to backend APIs over client-side bearer headers.
  - Rationale: the backend already accepts the opaque session cookie and this keeps the browser from handling the token value directly.
  - Alternative considered: issue short-lived frontend proxy tokens. Rejected as unnecessary complexity for the current protected business endpoints.

- Keep logout invalidation server-side.
  - Rationale: logout must invalidate the backend session without requiring client code to read the backend token.
  - Alternative considered: keep client-side logout calling the backend with a bearer token. Rejected because it preserves the token exposure being removed.

## Risks / Trade-offs

- Proxy route handlers add one frontend server hop for protected backend data -> keep handlers thin and endpoint-specific until a reusable pattern is justified.
- Cookie domain/path differences can break forwarding in local development -> verify cookie names and request headers in tests and local env examples.
- Auth.js JWT may still contain server-only backend data if callback code keeps it there -> tests should assert `useSession()` output and serialized session payload do not include backend session tokens.
- Logout ordering can become inconsistent between Auth.js and backend state -> implement a server-side logout helper/route and test backend invalidation before client auth state is cleared.

## Migration Plan

- Remove `backendSessionToken` from public NextAuth type augmentation and the `session` callback payload.
- Add frontend server-side route handler(s), starting with Home summary, that forward HttpOnly session cookies to the backend.
- Update client API functions and Home data fetching to call the frontend route handler instead of the backend directly with bearer auth.
- Update logout to invalidate the backend session through a server-side boundary before invoking Auth.js sign-out.
- Add regression tests for no token exposure, Home proxy behavior and logout invalidation path.
