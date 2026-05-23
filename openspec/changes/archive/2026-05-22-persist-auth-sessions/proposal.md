## Why

The authentication slice currently stores users, sessions and recovery tokens in process memory, so accounts and sessions disappear on restart and do not use the migrated PostgreSQL tables. This change closes that correctness gap by making authentication runtime persistence match the existing session and recovery-token contract.

## What Changes

- Replace the in-memory authentication repository with database-backed storage for users, sessions and recovery tokens.
- Persist registration data, Argon2id password hashes, `email_verified`, session records, invalidation state and recovery tokens in PostgreSQL.
- Validate protected backend endpoints against persisted session records instead of process-local dictionaries.
- Preserve existing public HTTP contracts for registration, credential verification, logout, recovery initiation and `GET /home/summary`.
- Keep Auth.js as the frontend authentication boundary while aligning backend session validation with persisted opaque tokens.
- Add integration tests that prove persistence, logout invalidation and recovery-token storage survive repository boundaries.

## Capabilities

### New Capabilities

- `persistent-auth-storage`: Database-backed user, session and recovery-token persistence for authentication flows.

### Modified Capabilities

- None.

## Impact

- Affects backend authentication repository, dependency wiring, API endpoints that create or validate sessions, test setup and database integration.
- Uses the existing Alembic-created auth tables for runtime persistence.
- May require SQLAlchemy async session wiring if it is not already available in the backend foundation.
- Frontend API contracts should remain unchanged for this change.
