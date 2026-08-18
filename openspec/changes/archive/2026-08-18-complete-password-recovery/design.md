## Context

Recovery initiation exists today: `POST /auth/recovery/request` generates a cleartext token (`token_urlsafe(32)`) and stores it in the `recovery_tokens` table with `expires_at`. `POST /auth/recovery/confirm` currently only admits the request and returns `{"status": "prepared"}` without validating or consuming a token. The frontend has `/forgot-password` but no token completion screen.

This change completes the loop. The existing shared abuse policy (`recovery_initiation` and `recovery_confirmation` categories) and session boundary already cover the surrounding security concerns, so this change focuses on token security, atomic confirmation, session revocation, delivery, and the frontend completion screen.

Stack: FastAPI + Pydantic + SQLAlchemy (async) backend, Next.js + Auth.js frontend, PostgreSQL with Alembic migrations.

## Goals / Non-Goals

**Goals:**

- Persist only a one-way hash of recovery tokens with explicit use state.
- Consume a token exactly once, atomically with the password update.
- Revoke all active sessions for the account after a successful reset.
- Add a frontend reset route with new-password and confirmation controls.
- Add a configurable delivery-provider boundary for the recovery link.
- Preserve neutral, enumeration-resistant responses throughout.

**Non-Goals:**

- No account email verification.
- No social authentication recovery.
- No retention of legacy cleartext recovery tokens.
- No token debugging exposed through production responses.

## Decisions

- **Token hashing**: store `hash_token(raw)` (SHA-256, optionally keyed) rather than the raw token. Lookup hashes the submitted token and matches the hash column. Keeps the table free of usable credentials.
- **One-time use**: add `used_at` and `invalidated_at` timestamp columns. A token is eligible only when `used_at IS NULL`, `invalidated_at IS NULL`, and `expires_at > now`.
- **Migration**: add new columns and drop/overwrite existing cleartext `token` values (invalidate rather than convert). No attempt to recover legacy tokens.
- **Atomic confirmation**: wrap hash lookup, conditional consume, password update, and session revocation in a single transaction using a conditional `UPDATE ... WHERE used_at IS NULL` to prevent concurrent replay.
- **Session revocation**: add a repository method that marks all non-revoked sessions for the user as invalidated in the same transaction.
- **Delivery boundary**: introduce a provider interface returning a recovery link from the configured public origin plus the single raw token. Production requires a configured delivery provider; development uses a controlled test sink that never logs the raw token.
- **Neutral responses**: confirmation returns the same body whether the token is unknown, expired, used, or invalidated. Schema-invalid payloads fall through deterministic 422 validation.
- **Password policy**: reuse the existing Argon2id hasher and the registration password length rule (minimum 8 characters) for the new password.

## Risks / Trade-offs

- Legacy cleartext tokens could be replayed if not invalidated → invalidate all during migration.
- Concurrent confirmation could double-consume → consume via conditional update under one transaction.
- Delivery configuration could leak tokens → provider boundary plus redacted logs; raw tokens never logged.
- Neutral errors reduce debuggability → offer a safe request-new-link path in the UI.

## Migration Plan

1. Add `token_hash`, `used_at`, and `invalidated_at` columns and indexes; invalidate existing cleartext rows.
2. Deploy backend initiation storing hashes and the confirmation transaction.
3. Deploy the frontend reset route after the backend contract is available.
