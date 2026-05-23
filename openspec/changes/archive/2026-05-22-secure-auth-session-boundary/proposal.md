## Why

The current frontend exposes the backend session token to client JavaScript by copying it into the Auth.js JWT/session and sending it as a bearer token from client components. This violates the opaque HttpOnly session boundary required for protected backend access and increases the impact of client-side script compromise.

## What Changes

- Keep backend session tokens server-only and unavailable from `useSession()` or other browser-readable session state.
- Stop sending backend session tokens as client-side bearer tokens from frontend components.
- Route protected backend business calls through a server-side frontend boundary that reads the HttpOnly session cookie and forwards the request securely.
- Preserve Auth.js as the frontend authentication boundary for login, logout and active frontend auth state.
- Keep public UI behavior for Home, logout and protected route redirects unchanged.
- Add tests proving the backend token is not exposed to client session data and Home data still loads through the server-side boundary.

## Capabilities

### New Capabilities
- `secure-auth-session-boundary`: Server-only handling of opaque backend session tokens for protected frontend-to-backend calls.

### Modified Capabilities
- None.

## Impact

- Affects frontend Auth.js callbacks/session shaping, Home data fetching, generated or transitional API client usage, logout behavior and tests.
- May add Next.js route handlers or server actions as a proxy boundary for protected backend business endpoints.
- Backend API contracts should remain unchanged, but frontend calls to protected backend endpoints will move out of client components.
