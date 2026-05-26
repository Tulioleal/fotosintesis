## Why

Authentication currently has two overlapping session concepts: Auth.js accepts the browser session from its JWT while the backend owns the persisted opaque session that can later be invalidated. This creates a mismatch with the intended persisted-session boundary and can allow frontend private routes to remain authenticated after the backend session is expired or invalidated.

## What Changes

- Align the frontend Auth.js boundary with backend persisted session validity instead of trusting only the Auth.js JWT payload for private access.
- Ensure private frontend route authorization checks a live backend persisted session or a server-only credential that is validated against the backend before allowing access.
- Keep backend session credentials out of browser-readable session data.
- Preserve the existing backend persisted opaque session model, idle refresh, absolute lifetime and logout invalidation behavior.
- Add regression tests proving invalidated or expired backend sessions cannot continue to authorize frontend private routes or protected frontend server route handlers.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `secure-auth-session-boundary`: tighten private frontend route authorization so Auth.js session state cannot outlive backend persisted session validity.
- `auth-cookie-bridge`: clarify that the server-only backend credential bridge must validate against persisted backend session records before protected frontend access succeeds.
- `persistent-auth-storage`: extend persisted session expectations to cover frontend boundary behavior after backend session invalidation or expiry.

## Impact

- Affects Auth.js configuration and callbacks in `frontend/auth.ts`.
- Affects private route protection in `frontend/src/middleware.ts` or an equivalent server-side route guard.
- Affects frontend server boundary helpers under `frontend/src/lib/server/` and route handlers under `frontend/src/app/api/`.
- May affect logout behavior in `frontend/src/components/layout/LogoutButton.tsx` and `frontend/src/app/api/auth/backend-logout/route.ts`.
- Adds frontend regression tests for invalidated/expired backend sessions at the route boundary and existing protected server route handlers.
- Backend API contracts should remain compatible; backend changes should be limited to validation support only if the frontend cannot validate efficiently with existing endpoints.
