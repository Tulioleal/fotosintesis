## 1. Data model and migration

- [x] 1.1 Add `token_hash`, `used_at`, and `invalidated_at` columns to `recovery_tokens` with indexes
- [x] 1.2 Add Alembic migration that invalidates or drops existing cleartext recovery tokens
- [x] 1.3 Update `RecoveryToken` model to carry hash and use-state instead of raw token

## 2. Token hashing and repository

- [x] 2.1 Add a token hashing helper and use it in recovery-token creation and lookup
- [x] 2.2 Update `create_recovery_token` to store only the hash and invalidate prior active tokens
- [x] 2.3 Add repository method to find an eligible token by hash with one-time-use check

## 3. Confirmation and revocation

- [x] 3.1 Add repository method to atomically consume a token and update the password in one transaction
- [x] 3.2 Add repository method to revoke all active sessions for a user
- [x] 3.3 Wire session revocation into the confirmation transaction

## 4. API

- [x] 4.1 Implement `POST /auth/recovery/confirm` to validate the token, password policy, and return neutral outcomes
- [x] 4.2 Reuse the shared recovery-confirmation limiter with neutral known/unknown behavior
- [x] 4.3 Add delivery-provider interface and configuration for recovery links with a development test sink

## 5. Frontend

- [x] 5.1 Add reset route reading the token without displaying it
- [x] 5.2 Build new-password and confirmation form with accessible labels and validation
- [x] 5.3 Wire BFF call and generated contracts for recovery confirmation
- [x] 5.4 Return to login with neutral completion notice and a request-new-link path on failure

## 6. Tests and acceptance

- [x] 6.1 Backend tests for token hashing, one-time replay, expiry, and invalidation
- [x] 6.2 Backend tests for atomic confirmation and concurrent replay yielding at most one success
- [x] 6.3 Backend tests for session revocation after reset and redaction of raw tokens
- [x] 6.4 Frontend tests for reset form and neutral failure behavior
- [x] 6.5 E2E test covering request, reset, re-login with new password, and old-password failure
