# Authentication Abuse Limits Policy

This document records the reviewed distributed authentication abuse policy
introduced by the `rate-limit-authentication-flows` change. It is the
authoritative reference for per-environment limits, windows, maximum retry
duration, retention, storage-failure policies, and the trusted source chain.
Thresholds are reviewed with security and operations before enforcement is
enabled in production and MUST be tuned only through validated configuration
(never code edits).

## Trusted Source Chain

Authentication traffic flows only through:

```
GKE Ingress -> Next.js (frontend) -> FastAPI (backend)
```

- GKE Ingress is the only public entry point. It populates a forwarding
  position whose exact value is documented in `docs/deployment/` and encoded
  in the frontend trusted-proxy configuration and tests.
- Next.js derives limiter source identity ONLY from that documented trusted
  forwarding position. Arbitrary client-supplied `Forwarded` or
  `X-Forwarded-For` values are ignored or conservatively collapsed.
- Before calling FastAPI, Next.js strips any client-supplied internal limiter
  headers and forwards an opaque keyed source digest plus an HMAC assertion
  produced with the dedicated internal assertion secret.
- FastAPI validates the assertion and NEVER treats arbitrary forwarding
  headers or unauthenticated source keys as identity. A missing or invalid
  assertion applies the conservative missing-source policy.

Direct public FastAPI authentication access is not part of the deployment
contract.

## Endpoint Categories and Dimensions

Every covered operation maps to a closed endpoint category. Limits apply per
category and dimension:

| Endpoint category               | Source dimension | Account dimension |
| ------------------------------- | ---------------- | ----------------- |
| `registration`                  | yes              | no                |
| `credential_verification`       | yes              | yes               |
| `recovery_initiation`           | yes              | yes               |
| `recovery_confirmation`         | yes              | yes (token-derived) |
| `authjs_post` (relevant Auth.js POST) | yes         | no                |

Account-derived keys use a versioned keyed HMAC digest; neither raw email
addresses nor raw source addresses are ever persisted, logged, or exposed.

## Per-Environment Defaults (Review Baseline)

These values are the baseline under review; deployed values live in the
environment `values.env` and are validated at startup.

| Setting | Local / dev | Prod baseline |
| ------- | ----------- | ------------- |
| Enforcement enabled | false | true |
| `registration` source limit | 10 / 1h | 10 / 1h |
| `credential_verification` source | 30 / 5m | 30 / 5m |
| `credential_verification` account | 5 / 5m | 5 / 5m |
| `recovery_initiation` source | 5 / 1h | 5 / 1h |
| `recovery_initiation` account | 2 / 1h | 2 / 1h |
| `recovery_confirmation` source | 5 / 5m | 5 / 5m |
| `recovery_confirmation` account | 2 / 1h | 2 / 1h |
| `authjs_post` source | 20 / 5m | 20 / 5m |
| Max `Retry-After` | 3600 s | 3600 s |
| Retention | 24 h | 24 h |

These are conservative starting values chosen to tolerate shared-NAT
aggregation; monitor only aggregate categories and tune through validated
configuration.

Enforcement is **mandatory in production**: startup refuses to boot when
`APP_ENV=prod|production` and `AUTH_LIMITER_ENABLED` is not `true`. Disabled
mode is available only for local, test, and dev. A missing or incorrect
production setting therefore fails startup instead of silently removing the
boundary.

## Storage-Failure Policies

Every covered endpoint fails closed when shared limiter storage is
unavailable. There is no bounded-fallback mode: a limiter-storage exception
must never admit authentication work, because a process-local fallback cannot
preserve the distributed bound.

| Endpoint category        | Storage failure behavior |
| ------------------------ | ------------------------ |
| `credential_verification`| fail closed (deny)       |
| `recovery_confirmation`  | fail closed (deny)       |
| `recovery_initiation`    | fail closed (neutral)    |
| `registration`           | fail closed (deny)       |
| `authjs_post`            | fail closed (deny)       |

Storage-failure responses are generic (503 with a bounded `Retry-After` for
non-recovery endpoints, neutral recovery contract for recovery endpoints) and
never reveal account state or storage details. Fail-open configuration is
explicitly rejected because it removes the security boundary exactly when
shared storage is unavailable. The complete limiter policy is validated during
application startup so an invalid production profile prevents boot.

## Response Contract

- Non-recovery limit rejection: `429 Too Many Requests` with an integer
  `Retry-After` clamped to the configured maximum; the body does not identify
  the exhausted key or disclose account existence.
- Recovery rejection: preserves the endpoint's neutral body and equivalent
  retry metadata for known and unknown accounts.
- Successful credential verification relaxes ONLY the account-specific
  credential-failure counter; source-wide and unrelated limits remain active.

## Recovery Confirmation Account Dimension

The `recovery_confirmation` account rule is derived from the submitted recovery
token through the same keyed digest path used for every other account key:
only an opaque keyed digest is ever persisted, logged, or exposed, never the
raw token. This makes the confirmation bound account-aware, so rotating source
addresses cannot bypass the token-specific limit. Schema-invalid payloads are
rejected by deterministic validation (`422`) before any token-state handling.
Token-shaped requests that reach token-state handling remain neutral regarding
token existence, expiration, or use. Volumetric malformed traffic is an
ingress/edge concern (Cloud Armor remains optional) and is not bounded by
application limits.

## Cleanup

Expired limiter windows are removed by an idempotent, bounded cleanup
operation that deletes only rows whose `window_end` has passed the configured
retention period (`AUTH_LIMITER_RETENTION_SECONDS`): rows inside retention are
preserved and rows beyond it are removed. Deployment scheduling is documented
in `docs/deployment/` and `deploy/k8s/`; retention is shorter than secret
retirement so HMAC rotation never resurrects stale keys.

## HMAC Key Rotation

- The configured key version is included in the HMAC **input** (`version`,
  dimension, identifier), not prefixed to stored values.
- Only one active key/version is currently supported; there is no overlap mode.
- Rotating the HMAC secret therefore resets or partitions the active counters:
  either accept the conservative counter reset (documented with operations) or
  partition counters per version. Retention (`AUTH_LIMITER_RETENTION_SECONDS`)
  stays shorter than secret retirement so stale digests never outlive keys.
- Never use fail-open configuration as a rotation or rollback mechanism.
