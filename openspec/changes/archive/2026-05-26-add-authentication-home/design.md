## Context

This slice creates the first authenticated product surface. It depends on the project foundation and should keep integrations to later features as navigational entry points or placeholders until those features exist.

The implementation is expected to run in the existing Fotosíntesis AI stack:

- Frontend: Next.js + React + TypeScript + SCSS Modules.
- Frontend server-state: TanStack Query for Home and business data only.
- Frontend client-state: Zustand only for temporary UI state.
- Backend: FastAPI + Pydantic + OpenAPI.
- Database: PostgreSQL with Alembic migrations.

## Goals / Non-Goals

**Goals:**

- Support registration, login, session persistence, logout and protected access.
- Use Auth.js / NextAuth as the frontend authentication boundary.
- Persist sessions with opaque HttpOnly cookies backed by backend/database session records.
- Provide a Home that reflects the intended MVP navigation and visual language.
- Handle loading, disabled, empty, error and retry states from the start.
- Provide navigable placeholders for future private features.
- Generate a typed frontend API client from the backend OpenAPI schema.
- Cover the slice with backend integration tests and frontend component/e2e tests.

**Non-Goals:**

- No completed plant identification, garden, reminders, assistant or light meter implementation.
- No real social login in this slice; social login may appear only as a disabled visual placeholder.
- No email delivery provider for password recovery in this slice.
- No advanced account management beyond registration, login, logout, session refresh and password recovery token initiation.

## Decisions

- Authentication strategy: Auth.js / NextAuth in the Next.js frontend.
- Public login, logout and session routes use Auth.js-generated routes.
- Sessions use opaque HttpOnly cookies backed by persisted session records.
- Session persistence is short-lived with automatic rolling refresh while the user remains active.
- Default session policy: 30 minutes idle TTL, rolling refresh on authenticated activity, and an absolute maximum lifetime of 7 days.
- Registration collects name, email and password.
- User records include an `email_verified` logical field. It does not block login in this slice.
- Social login is shown only as a disabled placeholder.
- Password recovery generates and stores a recovery token, but does not send email until a provider is added later.
- Password hashes use Argon2id.
- Login errors use neutral user-facing copy and record technical details only in backend logs.
- Auth validation is enforced server-side and reflected in frontend form states.
- Private frontend routes are protected with server-side redirection to `/login`.
- Protected backend APIs validate the same session requirement and return `401` for unauthenticated requests.
- Home starts at `/home` after login.
- Auth screens are separate routes: `/welcome`, `/login`, `/register`, `/forgot-password`.
- Home prioritizes plant identification as the main CTA and exposes secondary access to search, light meter, reminders, Mi Jardín and assistant.
- Pending features use navigable placeholders with “Próximamente” copy and no real domain logic.
- Home data is loaded from `GET /home/summary`.
- Home uses skeleton loading, recoverable error state and empty state for new users.
- UI copy uses neutral Spanish consistently.

## Implementation Contract

### Frontend routes

```text
/welcome
/login
/register
/forgot-password
/home
/identify              placeholder only
/search                placeholder only
/light-meter           placeholder only
/reminders             placeholder only
/garden                placeholder only
/assistant             placeholder only
```

### Auth.js routes

Auth.js owns the generated authentication/session routes, including sign-in, sign-out, session and credentials callback routes under the frontend API route namespace.

The application must not create competing custom login/logout/session routes with different behavior.

### Backend support endpoints

FastAPI remains responsible for domain validation, persistence support and protected business APIs.

```text
POST /auth/register
POST /auth/recovery/request
POST /auth/recovery/confirm        prepared endpoint; may remain non-UI-facing in this slice
POST /auth/credentials/verify      internal support endpoint for Auth.js Credentials provider, if needed
GET  /home/summary
GET  /health
GET  /metrics
```

If the implementation can verify credentials inside the Auth.js server runtime without a FastAPI support endpoint, `POST /auth/credentials/verify` may be omitted. The public contract must still be Auth.js-generated routes for login/logout/session.

### Request / response contracts

Registration request:

```json
{
  "name": "string",
  "email": "user@example.com",
  "password": "string"
}
```

Registration response:

```json
{
  "user": {
    "id": "string",
    "name": "string",
    "email": "user@example.com",
    "email_verified": false
  }
}
```

Password recovery request:

```json
{
  "email": "user@example.com"
}
```

Password recovery response:

```json
{
  "status": "ok",
  "message": "Si existe una cuenta con ese correo, te enviaremos instrucciones para recuperar el acceso."
}
```

Home summary response:

```json
{
  "user": {
    "id": "string",
    "name": "string",
    "email": "user@example.com"
  },
  "empty_state": true,
  "access": [
    { "key": "identify", "label": "Identificar planta", "href": "/identify", "status": "placeholder" },
    { "key": "search", "label": "Buscar plantas", "href": "/search", "status": "placeholder" },
    { "key": "light_meter", "label": "Medidor de luz", "href": "/light-meter", "status": "placeholder" },
    { "key": "reminders", "label": "Recordatorios", "href": "/reminders", "status": "placeholder" },
    { "key": "garden", "label": "Mi Jardín", "href": "/garden", "status": "placeholder" },
    { "key": "assistant", "label": "Asistente", "href": "/assistant", "status": "placeholder" }
  ]
}
```

### Validation

Frontend validation uses React Hook Form + Zod.

Backend validation uses Pydantic models and explicit endpoint rules.

Validation rules:

- `name`: required, trimmed, non-empty.
- `email`: required, valid email format, normalized to lowercase.
- `password`: required, at least 8 characters.
- Duplicate email: registration is rejected with a recoverable form error.
- Login failure: invalid password and nonexistent email use the same neutral user-facing message.
- Recovery email: invalid format is rejected; existing/non-existing accounts produce the same neutral confirmation after a syntactically valid request.

### Data model

Alembic migrations must create or update Auth.js-compatible tables, including users, accounts, sessions and verification/recovery tokens as needed by the selected Auth.js adapter.

The user record must support:

```text
id
name
email
email_verified logical field
password_hash
created_at
updated_at
```

`password_hash` must store Argon2id hashes only. Plaintext passwords must never be logged or persisted.

### Session and route protection

- Private frontend routes redirect server-side to `/login` when no valid session exists.
- Protected backend endpoints return `401` when no valid session exists.
- Logout invalidates the persisted session and clears frontend auth state.
- Refresh is automatic while the user is active and the session is within the absolute maximum lifetime.

### Frontend state management

- Auth session state is owned by Auth.js.
- TanStack Query is used for `GET /home/summary` and future server data.
- Zustand is used only for temporary UI state such as modal state, placeholder navigation state, local filters or onboarding UI.
- Zustand must not duplicate persisted backend data or Auth.js session data.

### Home and placeholders

Home must include:

- Primary CTA: “Identificar planta”.
- Visible search input that navigates to a placeholder route.
- Access cards for medidor de luz, recordatorios, Mi Jardín and assistant.
- Bottom navigation with Home, Identificar, Mi Jardín, Recordatorios and Asistente.
- Active Home section indicator.
- Skeleton loading state.
- Recoverable error state with retry.
- Empty state for users without saved plants or reminders.

Placeholder routes must:

- Require authentication.
- Preserve the main layout and bottom navigation.
- Show neutral Spanish “Próximamente” copy.
- Avoid implementing real plant, garden, reminder, assistant or light-meter logic.

### Typed API client

The frontend should consume backend business endpoints through a generated OpenAPI client.

Manual TypeScript DTO duplication should be avoided unless the generator is not yet available; in that case, temporary types must be clearly marked as transitional.

### Testing strategy

Backend:

- Integration tests for registration support endpoint.
- Integration tests for password recovery request.
- Integration tests for protected `GET /home/summary` with valid and invalid sessions.
- Integration tests proving protected APIs reject unauthenticated requests.
- Validation tests for invalid email, short password, duplicate email and neutral login/recovery behavior.

Frontend:

- React Testing Library tests for auth forms, validation states, disabled/loading states and Home states.
- Playwright tests for registration/login flow, unauthenticated private-route redirection, Home rendering and placeholder navigation.

## Risks / Trade-offs

- Auth.js with a separate FastAPI backend requires a clear session validation boundary. The implementation must avoid two competing session systems.
- Password recovery token generation without an email provider is useful for future integration but does not complete the real-world recovery loop.
- Home links to features that are intentionally pending; placeholder routes reduce dead ends but must not be confused with implemented domain functionality.
- Auth.js-compatible tables managed through Alembic may require careful naming/mapping depending on the selected Auth.js adapter.
