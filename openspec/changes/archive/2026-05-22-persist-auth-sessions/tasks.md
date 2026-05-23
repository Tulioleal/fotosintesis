## 1. Database Access Foundation

- [x] 1.1 Add SQLAlchemy async runtime dependency if it is not already available to the backend package
- [x] 1.2 Add backend database engine and async session dependency wiring using `Settings.database_url`
- [x] 1.3 Add metadata/table mappings or minimal SQLAlchemy models for `users`, `sessions` and `recovery_tokens`
- [x] 1.4 Add a test database/session fixture or dependency override that isolates auth persistence tests

## 2. Persistent Auth Repository

- [x] 2.1 Replace `InMemoryAuthRepository` dictionary storage with database-backed repository operations
- [x] 2.2 Persist registered users with normalized email, Argon2id password hash and `email_verified=false`
- [x] 2.3 Verify credentials from persisted user records without logging or returning plaintext-sensitive details
- [x] 2.4 Persist sessions with opaque token, idle expiration, absolute expiration and invalidation fields
- [x] 2.5 Refresh valid persisted sessions within the absolute maximum lifetime during protected access
- [x] 2.6 Persist recovery tokens with expiration and optional user association

## 3. API And Dependency Integration

- [x] 3.1 Update auth endpoints to await database-backed repository operations
- [x] 3.2 Update `get_current_user` and `get_current_session` to validate persisted sessions
- [x] 3.3 Preserve existing response contracts and status codes for registration, credentials verification, logout, recovery request and Home summary
- [x] 3.4 Ensure logout invalidates the persisted session before clearing the session cookie
- [x] 3.5 Confirm existing Alembic auth tables satisfy runtime repository needs or add a minimal migration for any discovered schema gap

## 4. Tests And Verification

- [x] 4.1 Add backend integration test proving registered users are persisted and can be verified through a fresh repository/session scope
- [x] 4.2 Add backend integration test proving credential verification creates a persisted session record
- [x] 4.3 Add backend integration test proving protected `GET /home/summary` accepts valid persisted sessions and rejects missing, invalidated or expired sessions with `401`
- [x] 4.4 Add backend integration test proving recovery requests persist expiring recovery tokens while returning neutral copy
- [x] 4.5 Run backend tests and update any affected fixtures or setup documentation needed for local execution
