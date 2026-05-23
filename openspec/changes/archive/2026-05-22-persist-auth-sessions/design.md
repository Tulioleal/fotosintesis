## Context

The current authentication implementation exposes the expected HTTP contracts, but runtime state is stored in `InMemoryAuthRepository`. Users, password hashes, sessions and recovery tokens therefore only exist inside one backend process and are lost on restart. The existing `0002_authentication_home` migration already defines `users`, `accounts`, `sessions`, `verification_tokens` and `recovery_tokens`, but the application does not use those tables at runtime.

This change makes the backend authentication storage durable while preserving the current frontend and backend API contracts.

## Goals / Non-Goals

**Goals:**

- Store users, password hashes, `email_verified`, sessions and recovery tokens in PostgreSQL.
- Validate protected backend requests against persisted session records.
- Preserve registration, credential verification, logout, recovery initiation and Home summary response contracts.
- Keep Argon2id password hashing and neutral authentication error behavior.
- Add integration tests for durable auth storage, session invalidation and recovery-token persistence.

**Non-Goals:**

- No new user-facing authentication screens.
- No email provider integration or full password reset completion flow.
- No social login provider implementation.
- No frontend session-boundary redesign beyond what is necessary to keep current backend calls working.
- No replacement of Auth.js as the frontend authentication boundary.

## Decisions

- Use SQLAlchemy async engine/session wiring for database access.
  - Rationale: the backend already uses FastAPI async handlers and the configured database URL is `postgresql+asyncpg`.
  - Alternative considered: direct `asyncpg` queries. Rejected because SQLAlchemy integrates better with Alembic table metadata and dependency-managed sessions.

- Keep repository methods as the authentication storage boundary, but make them async and database-backed.
  - Rationale: API endpoints and dependencies already depend on repository operations, so replacing the implementation minimizes route-level churn.
  - Alternative considered: move SQL directly into endpoint handlers. Rejected because it couples HTTP behavior to persistence details.

- Use the existing migrated tables instead of adding a new migration unless a schema gap is discovered during implementation.
  - Rationale: `users`, `sessions` and `recovery_tokens` already contain the columns needed by the current contracts.
  - Alternative considered: create replacement tables with different names. Rejected because it would duplicate existing Auth.js-compatible schema intent.

- Continue storing Argon2id hashes only in `users.password_hash`.
  - Rationale: preserves existing credential verification behavior and keeps plaintext passwords out of storage and logs.

- Treat session token lookup as the source of truth for protected backend endpoints.
  - Rationale: `GET /home/summary` and logout already validate opaque tokens; durable storage makes that validation consistent across process restarts.

## Risks / Trade-offs

- Database availability becomes required for auth flows -> return existing error semantics where possible and let health/operational monitoring expose database failures.
- Tests need a database strategy -> use dependency overrides or isolated transactional sessions so tests do not share production state.
- Async repository changes touch multiple call sites -> update endpoint and dependency functions together and rely on typecheck/tests to catch missed awaits.
- Existing in-memory tests may rely on implicit clean state -> reset database tables or run each integration test in an isolated transaction.

## Migration Plan

- Confirm `0002_authentication_home` is applied in local and deployed environments before enabling the database-backed repository.
- Add SQLAlchemy engine/session dependency wiring using the existing `database_url` setting.
- Replace in-memory repository operations with SQL-backed operations against the existing auth tables.
- Run backend integration tests against migrated schema.
- Rollback strategy: revert the repository wiring and code changes; no destructive migration is expected for this change.

## Open Questions

- The test database provisioning command is not currently documented in the change; implementation should follow the project’s available local PostgreSQL setup or add minimal test setup documentation if missing.
