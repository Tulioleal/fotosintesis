## Why

The MVP needs a protected mobile-first entry point before private plant, assistant and garden features can be used. Authentication and Home establish the first complete user-facing flow.

This slice must also establish the authentication contract that later private features will reuse.

## What Changes

- Implement Auth.js / NextAuth authentication in the Next.js frontend.
- Use opaque HttpOnly session cookies backed by persisted backend/database session records.
- Implement short-lived session persistence with automatic refresh while the user remains active.
- Implement registration with required-field, email, password length and duplicate email validation.
- Store user passwords with Argon2id hashes.
- Include `email_verified` user state without blocking login in this slice.
- Implement login through Auth.js-generated routes and neutral user-facing login errors.
- Implement server-side redirection for unauthenticated private frontend routes.
- Implement protected backend API access with `401` responses for unauthenticated requests.
- Implement logout by invalidating the persisted session and clearing frontend auth state.
- Implement password recovery initiation by generating and storing a token without sending email yet.
- Build `/welcome`, `/login`, `/register` and `/forgot-password` screens with loading, disabled and error states.
- Show disabled visual placeholders for social login without implementing social auth.
- Build Home at `/home` with identification CTA, search, medidor de luz, recordatorios, Mi Jardín and assistant access.
- Load Home data from `GET /home/summary`.
- Implement Home skeleton, empty, error and retry states.
- Add navigable authenticated placeholder routes for pending features using “Próximamente” copy.
- Apply Fotosíntesis visual identity, bottom navigation and neutral Spanish tone consistently.
- Use React Hook Form + Zod for frontend form validation.
- Use Pydantic and explicit rules for backend validation.
- Use TanStack Query for Home server data while keeping auth state owned by Auth.js.
- Use Zustand only for temporary UI state.
- Generate the frontend API client from backend OpenAPI when consuming backend business endpoints.
- Add backend integration tests and frontend React Testing Library + Playwright tests.

## Capabilities

### New Capabilities

- `authentication-home`: authentication, protected access and mobile-first Home experience.

### Modified Capabilities

- None.

## Impact

- Affects frontend auth screens, Auth.js configuration, session state, route protection, backend auth support endpoints, backend session validation, database migrations, generated OpenAPI client usage and Home UI.
- Adds or updates Auth.js-compatible database tables through Alembic migrations.
- Adds `GET /home/summary` as the initial protected Home data endpoint.
- Keeps plant identification, search, medidor de luz, recordatorios, Mi Jardín and assistant as authenticated placeholders only.
