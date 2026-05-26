## 1. Session Validation Boundary

- [x] 1.1 Identify the existing server-only credential resolution path used by protected frontend route handlers
- [x] 1.2 Add or reuse a backend session validation request that returns success only for valid persisted sessions and `401` for missing, expired or invalidated sessions
- [x] 1.3 Ensure validation uses only HttpOnly cookies or server-only Auth.js token state and never browser-readable session data
- [x] 1.4 Keep backend session tokens out of Auth.js browser-visible `session()` payloads

## 2. Private Route Protection

- [x] 2.1 Update private frontend route protection for `/home`, `/identify`, `/search`, `/light-meter`, `/reminders`, `/garden` and `/assistant` to validate backend persisted session state
- [x] 2.2 Redirect server-side to `/login` with callback URL when backend session validation fails
- [x] 2.3 Allow private routes to render when backend session validation succeeds
- [x] 2.4 Avoid redirect loops by limiting validation to private routes only

## 3. Protected Route Handlers And Logout

- [x] 3.1 Ensure `/api/home/summary` rejects stale Auth.js state when the backend persisted session is expired or invalidated
- [x] 3.2 Ensure `/api/auth/backend-logout` invalidates the backend persisted session through the server-side boundary
- [x] 3.3 Ensure private route access redirects after backend logout even if stale Auth.js state remains temporarily present
- [x] 3.4 Preserve backend idle refresh and absolute lifetime behavior during validation

## 4. Tests

- [x] 4.1 Add frontend tests for private route rejection when no backend session credential exists
- [x] 4.2 Add frontend tests for private route rejection when Auth.js state exists but backend validation returns `401`
- [x] 4.3 Add frontend tests for private route success when backend validation succeeds
- [x] 4.4 Add route-handler tests for stale login-created credentials returning unauthorized from protected frontend endpoints
- [x] 4.5 Keep or extend token non-exposure tests proving browser-visible session data excludes backend credentials
- [x] 4.6 Run `npm run typecheck` and `npm test` in `frontend`
- [x] 4.7 Run `pytest` in `backend` if backend validation code changes
