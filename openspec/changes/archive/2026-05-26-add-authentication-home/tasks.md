## 1. Authentication And Home

### 1.1 Auth architecture and persistence

- [x] 1.1.1 Configure Auth.js / NextAuth in the Next.js frontend
- [x] 1.1.2 Configure Auth.js-generated routes for sign-in, sign-out and session handling
- [x] 1.1.3 Implement opaque HttpOnly cookie sessions backed by persisted session records
- [x] 1.1.4 Configure short session TTL, rolling refresh and absolute maximum lifetime
- [x] 1.1.5 Add Alembic migrations for Auth.js-compatible users, accounts, sessions and token tables
- [x] 1.1.6 Add `email_verified` logical user state without blocking login

### 1.2 Registration and credential handling

- [x] 1.2.1 Implement registration with name, email and password
- [x] 1.2.2 Validate required fields, email format, password length and duplicate email
- [x] 1.2.3 Hash passwords with Argon2id before persistence
- [x] 1.2.4 Use React Hook Form + Zod for frontend registration validation
- [x] 1.2.5 Use Pydantic and explicit backend rules for registration validation

### 1.3 Login, logout and protected access

- [x] 1.3.1 Implement credential login through Auth.js
- [x] 1.3.2 Show neutral user-facing login errors and keep technical reasons in logs only
- [x] 1.3.3 Implement server-side redirects from private frontend routes to `/login`
- [x] 1.3.4 Validate sessions on protected backend endpoints and return `401` when unauthenticated
- [x] 1.3.5 Implement logout by invalidating the persisted session and clearing frontend auth state

### 1.4 Password recovery initiation

- [x] 1.4.1 Implement password recovery request with valid email format validation
- [x] 1.4.2 Generate and persist a recovery token with expiration
- [x] 1.4.3 Return neutral confirmation copy regardless of whether the email exists
- [x] 1.4.4 Leave email delivery integration out of scope
- [x] 1.4.5 Prepare recovery confirmation endpoint or service contract for future email-provider integration

### 1.5 Auth screens

- [x] 1.5.1 Build `/welcome`
- [x] 1.5.2 Build `/login`
- [x] 1.5.3 Build `/register`
- [x] 1.5.4 Build `/forgot-password`
- [x] 1.5.5 Add loading, disabled, focus, error and retry states to auth screens
- [x] 1.5.6 Add disabled visual placeholder for social login
- [x] 1.5.7 Apply neutral Spanish copy consistently

### 1.6 Home

- [x] 1.6.1 Implement protected `/home` route as the post-login destination
- [x] 1.6.2 Implement protected `GET /home/summary`
- [x] 1.6.3 Generate or update frontend OpenAPI client for backend business endpoints
- [x] 1.6.4 Load Home data with TanStack Query
- [x] 1.6.5 Build Home with primary identification CTA, search, medidor de luz, recordatorios, Mi Jardín and assistant access
- [x] 1.6.6 Implement Home skeleton loading state
- [x] 1.6.7 Implement Home empty state for new users
- [x] 1.6.8 Implement Home recoverable error state with retry

### 1.7 Placeholder navigation

- [x] 1.7.1 Add authenticated placeholder route for `/identify`
- [x] 1.7.2 Add authenticated placeholder route for `/search`
- [x] 1.7.3 Add authenticated placeholder route for `/light-meter`
- [x] 1.7.4 Add authenticated placeholder route for `/reminders`
- [x] 1.7.5 Add authenticated placeholder route for `/garden`
- [x] 1.7.6 Add authenticated placeholder route for `/assistant`
- [x] 1.7.7 Ensure placeholders show “Próximamente” copy and no real domain logic

### 1.8 Navigation and visual identity

- [x] 1.8.1 Implement bottom navigation with Home, Identificar, Mi Jardín, Recordatorios and Asistente
- [x] 1.8.2 Show active section state in bottom navigation
- [x] 1.8.3 Apply Fotosíntesis visual identity using SCSS Modules
- [x] 1.8.4 Use Zustand only for temporary UI state and avoid duplicating Auth.js or backend data

### 1.9 Tests and acceptance

- [x] 1.9.1 Add backend integration tests for registration validation
- [x] 1.9.2 Add backend integration tests for password recovery token initiation
- [x] 1.9.3 Add backend integration tests for protected endpoint access with valid and invalid sessions
- [x] 1.9.4 Add frontend React Testing Library tests for auth forms and Home states
- [x] 1.9.5 Add Playwright tests for registration/login, unauthenticated redirect, Home rendering and placeholder navigation
- [x] 1.9.6 Ensure the implementation includes code and tests with no unresolved TODOs for this slice
