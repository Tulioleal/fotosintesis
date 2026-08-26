## Why

Registration, credential verification, and password recovery currently lack a distributed inbound abuse boundary, leaving the application exposed to credential stuffing, password-hash CPU exhaustion, recovery flooding, token growth, and repeated token guesses. Because production runs multiple Kubernetes replicas, authentication-sensitive operations need one observable, enumeration-resistant policy backed by shared enforcement state.

## What Changes

- Add distributed source-aware and normalized account-aware limits for registration, credential verification, recovery initiation, recovery confirmation, and relevant Auth.js POST operations.
- Derive source identity only from the documented trusted GKE ingress and proxy chain, never from arbitrary forwarding headers.
- Return bounded `429 Too Many Requests` responses and `Retry-After` metadata while preserving neutral recovery responses for known and unknown accounts.
- Define endpoint-specific fail-closed or strictly bounded behavior when limiter storage is unavailable.
- Add retention and cleanup for limiter state plus bounded metrics for allowed, rejected, and storage-failure outcomes without sensitive identifiers.
- Handle `429` responses and retry timing in authentication forms.
- Verify concurrency bounds, spoofing resistance, response contracts, storage-failure behavior, and enforcement across replicas.
- Keep optional volumetric edge protection separate from account-sensitive application limits.

## Capabilities

### New Capabilities

- `authentication-abuse-controls`: Shared distributed limits, trusted request identity, safe failure behavior, retry contracts, privacy-preserving observability, and limiter-state lifecycle for authentication-sensitive operations.

### Modified Capabilities

- `authentication-home`: Registration, login, and recovery forms enforce and present bounded abuse responses without weakening neutral authentication behavior.
- `persistent-auth-storage`: Persistent authentication storage supports atomic, expiring shared limiter state when database-backed enforcement is configured.
- `secure-auth-session-boundary`: Authentication-facing proxy boundaries derive limiter source identity only through the trusted ingress chain and safely constrain relevant Auth.js POST operations.
- `testing-deployment`: Deployment and test contracts verify distributed enforcement, concurrency bounds, trusted proxy behavior, safe metrics, and optional edge protection separation.

## Impact

- Backend authentication endpoints, services, repository interfaces, configuration, database migrations, metrics, and cleanup operations.
- Frontend Auth.js handlers and authentication forms, including typed `429` and retry behavior.
- GKE ingress/proxy trust configuration, Kubernetes runtime settings, dashboards, and deployment documentation.
- Backend, frontend, integration, concurrency, and multi-replica test suites.
- Depends on `upgrade-authjs-security-boundary`; recovery limits must be available before `complete-password-recovery` releases recovery initiation and confirmation.
