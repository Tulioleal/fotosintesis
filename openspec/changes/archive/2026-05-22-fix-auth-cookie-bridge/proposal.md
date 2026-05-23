## Why

The frontend now routes protected Home and logout calls through server-side boundaries, but login does not establish a browser cookie that those boundaries can forward. Without a secure bridge from backend credential verification to browser HttpOnly session state, users can authenticate with Auth.js yet still fail protected backend calls after login.

## What Changes

- Ensure successful credential login propagates the backend session into browser HttpOnly cookie state usable by frontend route handlers.
- Keep the backend session token unavailable from browser-readable Auth.js session data and client JavaScript.
- Preserve the `/api/home/summary` and `/api/auth/backend-logout` server-side boundary model.
- Add regression coverage proving login-created session state authenticates Home through the frontend boundary without client-side bearer token exposure.

## Capabilities

### New Capabilities
- `auth-cookie-bridge`: Secure bridging of backend credential sessions into frontend server-readable HttpOnly cookie state.

### Modified Capabilities
- None.

## Impact

- Affects frontend Auth.js credential authorization, session/cookie handling, protected route handlers and frontend tests.
- Backend authentication contracts should remain unchanged.
- No new user-facing screens or authentication providers are expected.
