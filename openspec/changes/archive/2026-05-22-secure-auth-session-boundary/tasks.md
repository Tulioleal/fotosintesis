## 1. Remove Client-Visible Backend Tokens

- [X] 1.1 Remove `backendSessionToken` from browser-visible NextAuth session type augmentation
- [X] 1.2 Update Auth.js callbacks so `session()` does not copy the backend session token into the returned session payload
- [X] 1.3 Audit client components and browser-executed helpers for backend session token reads
- [X] 1.4 Remove client-side `Authorization: Bearer <backend session token>` usage for protected backend business endpoints

## 2. Add Server-Side Protected Data Boundary

- [X] 2.1 Add a frontend server-side route handler or server action for Home summary data
- [X] 2.2 Forward the HttpOnly backend session cookie or server-only credential from the frontend server boundary to `GET /home/summary`
- [X] 2.3 Return backend unauthorized and error responses from the frontend boundary without exposing credential details
- [X] 2.4 Update the Home client data fetcher to call the frontend-owned boundary instead of the backend directly
- [X] 2.5 Preserve TanStack Query loading, retry and error behavior for Home

## 3. Secure Logout Flow

- [X] 3.1 Add a frontend server-side logout boundary that invalidates the backend session without client token access
- [X] 3.2 Update `LogoutButton` to call the server-side logout boundary and then clear Auth.js frontend state
- [X] 3.3 Ensure logout still redirects to `/login` and does not expose backend credential values in responses or logs

## 4. Tests And Verification

- [X] 4.1 Add frontend unit test proving browser-visible session data does not include `backendSessionToken` or equivalent backend bearer credential
- [X] 4.2 Add frontend test proving Home requests use the frontend boundary and do not send backend bearer tokens from client code
- [X] 4.3 Add route-handler or integration test for Home summary proxy success and unauthorized responses
- [X] 4.4 Add logout test proving backend invalidation is triggered through the server-side boundary
- [X] 4.5 Run frontend typecheck and tests after removing token exposure
