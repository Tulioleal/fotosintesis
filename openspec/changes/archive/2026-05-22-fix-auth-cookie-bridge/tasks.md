## 1. Server-Only Credential Retention

- [x] 1.1 Store the backend `session_token` from credentials login in Auth.js JWT server state
- [x] 1.2 Keep `session()` output and NextAuth `Session` type free of backend token or bearer credential fields
- [x] 1.3 Remove or internalize any public type names that encourage browser-readable backend token access

## 2. Protected Boundary Credential Resolution

- [x] 2.1 Add a small server-only helper that resolves backend request credentials from Auth.js server state or incoming HttpOnly cookie state
- [x] 2.2 Update `/api/home/summary` to authenticate backend `GET /home/summary` using the resolved server-only credential
- [x] 2.3 Update `/api/auth/backend-logout` to authenticate backend `POST /auth/logout` using the resolved server-only credential
- [x] 2.4 Preserve unauthorized and generic error responses without returning credential values

## 3. Regression Tests

- [x] 3.1 Add frontend test proving Auth.js browser-visible session data does not include the retained backend credential
- [x] 3.2 Add route-handler test proving `/api/home/summary` can use login-created server-only Auth.js state without a manually supplied backend cookie
- [x] 3.3 Add route-handler test proving `/api/auth/backend-logout` invalidates using login-created server-only Auth.js state
- [x] 3.4 Keep or update tests proving existing HttpOnly cookie forwarding still works

## 4. Verification

- [x] 4.1 Run frontend typecheck
- [x] 4.2 Run frontend tests
- [x] 4.3 Re-run the secure session boundary token audit to confirm no client-side bearer usage returns
