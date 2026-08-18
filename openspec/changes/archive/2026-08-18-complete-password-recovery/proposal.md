## Why

The backend creates recovery tokens but never consumes them, the confirmation endpoint does not change the account password, and the frontend has no completion screen. Tokens are persisted in cleartext and do not record one-time use. The recovery flow must become secure and functional end to end.

## What Changes

- Generate cryptographically strong opaque recovery tokens and persist only a one-way hash.
- Retain expiration and add consumed or used timestamp metadata.
- Invalidate all existing cleartext recovery tokens through migration.
- Add atomic lookup, validation, consumption, and password update behavior.
- Add backend confirmation behavior accepting a token and new password.
- Validate new passwords under the existing registration password policy.
- Store the replacement password using Argon2id.
- Revoke all active sessions for the account after successful reset.
- Add a frontend reset route with token and new-password controls.
- Preserve neutral initiation responses that do not reveal account existence.
- Add a configurable secure recovery-link delivery boundary.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `authentication-home`: complete recovery confirmation and frontend completion flow.
- `persistent-auth-storage`: hashed one-time recovery tokens and session revocation.

## Impact

- Add token hash, used timestamp, and invalidation fields through migration.
- Update auth repository methods and recovery confirmation endpoint schemas.
- Add session-revocation repository behavior.
- Add frontend reset route, form validation, BFF calls, and generated contracts.
- Add delivery-provider configuration and local testing support.
- Update authentication unit, integration, and E2E tests.
