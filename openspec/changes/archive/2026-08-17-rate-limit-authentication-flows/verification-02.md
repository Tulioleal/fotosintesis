# Verification Report: rate-limit-authentication-flows

Verified on 2026-08-15 against the change proposal, design, five delta
specifications, 33 checked tasks, implementation, tests, generated contracts,
and rendered production manifests. This is `verification-02.md` and it
compares every finding from `verification-01.md` as fixed, remaining, or
regressed.

## Summary

| Dimension | Status |
|---|---|
| Completeness | 33/33 tasks marked complete and supported by runtime behavior + focused negative tests |
| Correctness | All 5 critical and all 9 warning findings from verification-01 addressed |
| Coherence | Trust boundary, storage failure, Auth.js POST, retry contract, recovery confirmation, and deployment now follow the design |
| Archive readiness | Ready to archive |

## Findings Comparison (verification-01 -> verification-02)

### Critical Findings

#### 1. Production source identity selects the load balancer address — FIXED

**verification-01:** `extractTrustedClientAddress()` selected the final
`X-Forwarded-For` entry under the production `gke-last` policy, which is the
load-balancer address on the Google external Application Load Balancer.

**fix:** Recorded the authoritative external ALB contract (the load balancer
appends `<client-ip>,<load-balancer-ip>`; the final entry is the load
balancer; preceding entries are unverified client input). Replaced the
ambiguous `gke-last` position with an explicit trusted-hop policy:
`AUTH_LIMITER_TRUSTED_FORWARDED_HOPS=2` in production
(`frontend/src/lib/server/source-identity.ts`). The client is the first of the
two trailing platform-appended entries; a single trusted hop or a malformed or
short chain fails conservatively (null source). Added representative GKE
header tests, attacker-prepended entries, malformed chains, and missing-chain
behavior (`frontend/src/lib/server/source-identity.test.ts`, 21 tests). The
load-balancer address is never selected as the client and the deployment
values/docs now document `2`.

Reference (fetched 2026-08-15):
https://cloud.google.com/load-balancing/docs/https (`X-Forwarded-For` header).

#### 2. Relevant Auth.js POST operations are not rate limited — FIXED

**verification-01:** The Auth.js route exported its raw POST handler and no
runtime code evaluated `EndpointCategory.authjs_post`.

**fix:** Added a narrow internal backend admission endpoint
`POST /auth/admit/authjs_post` protected by the same signed source assertion
(`backend/app/api/auth.py`) and wrapped the Auth.js POST handler
(`frontend/src/app/api/auth/[...nextauth]/route.ts`). The wrapper enforces the
distributed `authjs_post` source policy before invoking Auth.js for relevant
unauthenticated actions (credentials callback, CSRF, sign-in) and never limits
GET session reads, authenticated session updates, or sign-out. On rejection it
emits the Auth.js-compatible error redirect carrying the bounded error code so
the login form surfaces it. Backend tests cover the endpoint (admission,
repeated rejection across shared state, missing-source, storage failure);
frontend tests cover GET passthrough, logout/session-update passthrough,
bounded 429/503, and source assertion forwarding (route.test.ts, 6 tests).
`EndpointCategory.authjs_post` now has a real runtime call site and the metric
records all three closed outcomes.

#### 3. `bounded_fallback` is unbounded fail-open behavior — FIXED

**verification-01:** Every limiter-storage exception configured as
`bounded_fallback` returned `allowed` without a local counter, window, lock, or
admission bound.

**fix:** Removed `bounded_fallback` from `StorageFailureMode`; the enum now
supports only `fail_closed` (`backend/app/limiter/policy.py`). The limiter
service always fails closed on storage exceptions
(`backend/app/limiter/service.py`). `test_auth_limiter_lifecycle.py` proves a
storage exception never admits authentication work and an unknown
storage-failure mode prevents startup.

#### 4. Rendered limiter ConfigMap values are not strings — FIXED

**verification-01:** Limiter boolean/numeric substitutions were unquoted and
the deployment test expected a YAML boolean.

**fix:** Quoted every `ConfigMap.data` value in `deploy/k8s/base/20-config.yaml`
(including all limiter settings). `test_rendered_configmap_values_are_all_strings`
asserts every data value is a string, and `test_prod_limiter_enforcement_enabled_as_string`
replaced the boolean expectation. Rendered manifests were independently
inspected for dev and prod.

#### 5. The cleanup CronJob lacks Cloud SQL connectivity — FIXED

**verification-01:** The cleanup job had `DATABASE_URL` but no Cloud SQL Auth
Proxy sidecar.

**fix:** Added a Cloud SQL Auth Proxy native sidecar (init container with
`restartPolicy: Always`) to `deploy/k8s/base/56-limiter-cleanup.yaml` using the
same reviewed pattern as the migration/backend workloads, plus the proxy-ready
wait before running `scripts.cleanup_limiter_state`.
`test_limiter_cleanup_cronjob_can_reach_cloud_sql_via_proxy_sidecar` verifies
the sidecar, connection arguments, workload-identity label, and cleanup command.

### Warnings

#### 1. Forms ignore authoritative `Retry-After` — FIXED

**verification-01:** Registration and recovery always blocked for 60 seconds
and Auth.js discarded the credential retry duration.

**fix:** Added a documented bounded error-code mechanism
(`frontend/src/lib/server/auth-rate-limit.ts`): `encodeRetryCode` /
`parseRetryCode` carry the clamped whole-second delay in the Auth.js `code`
(e.g. `credentials_rate_limited:37`). The Auth.js `CredentialsRateLimited`
error carries `retryAfterSeconds` and encodes it; the login form parses the
actual server duration. Registration and recovery forms use
`ApiClientError.retryAfterSeconds` (clamped) instead of a fixed 60s. Tests
cover 1-second, short, maximum, malformed, and missing retry headers
(`auth-rate-limit.test.ts`), and component tests assert the deadline uses the
server value. E2E 429 journeys verify the countdown re-enables the forms.

#### 2. Authentication route handlers propagate raw client headers — FIXED

**verification-01:** Registration and recovery cloned all request headers and
removed only internal limiter headers.

**fix:** Internal requests are built from an allowlist
(`buildInternalAuthHeaders` in `frontend/src/lib/server/source-identity.ts`):
only `Content-Type: application/json` plus the generated source key/assertion.
Route tests prove cookies, forwarding headers, and forged internal limiter
headers never reach FastAPI (`register/route.test.ts`,
`recovery/request/route.test.ts`, `[...nextauth]/route.test.ts`).

#### 3. Recovery confirmation lacks the documented account dimension — FIXED

**verification-01:** Production policy set the recovery-confirmation account
profile to null and the endpoint supplied no account identifier.

**fix:** The confirmation endpoint now derives the account dimension from the
submitted token through the existing keyed digest path
(`backend/app/api/auth.py`); only an opaque keyed digest is persisted, never
the raw token. Prod/dev profiles configure the documented account rule
(2 / 1h). Tests prove rotating sources cannot bypass the token-bound limit,
different tokens are independent account keys, persisted state contains no raw
token, schema-invalid payloads are deterministic 422 validation errors without
token-state detail, and token-shaped requests that reach token-state handling
are neutral regarding token existence, expiration, or use
(`tests/test_auth_limiter.py`, `tests/test_auth_limiter_privacy.py`).

#### 4. Retention configuration is unused — FIXED

**verification-01:** Cleanup deleted rows as soon as `window_end < now`,
ignoring `AUTH_LIMITER_RETENTION_SECONDS`.

**fix:** `LimiterRepository.cleanup` now takes `retention_seconds` and removes
only rows whose window ended before `now - retention`; rows inside retention
are preserved. The service and cleanup script pass the configured retention.
`test_auth_limiter_lifecycle.py` proves rows inside retention survive and rows
beyond it are removed, and the integration cleanup race seeds both expired and
active rows.

#### 5. Generated error contracts do not match runtime responses — FIXED

**verification-01:** `RateLimitResponse` required `retry_after_seconds` in the
JSON body while runtime bodies contained only `detail`; generated responses
omitted a typed `Retry-After` header.

**fix:** `RateLimitResponse` now declares only `detail`
(`backend/app/auth/schemas.py`), matching the runtime body, and every 429/503
route response documents the `Retry-After` integer response header
(`backend/app/api/auth.py`). The OpenAPI baseline and typed frontend client
were regenerated; `test_limited_response_matches_the_documented_detail_and_retry_after_contract`
asserts the body keys and header, and `check-openapi.mjs` and the snapshot test
pass.

#### 6. Retry calculation can emit zero during an active window — FIXED

**verification-01:** `int()` flooring could return `Retry-After: 0`.

**fix:** The repository rounds remaining time up with `math.ceil` and enforces
a minimum of 1 second for an active rejection (`backend/app/limiter/repository.py`).
`test_active_rejection_never_returns_zero_retry` and
`test_retry_delay_rounds_up_from_a_partial_window` cover sub-second remaining
windows deterministically.

#### 7. Multi-rule and multi-replica tests overstate their evidence — FIXED

**verification-01:** The rollback test exhausted equal limits (rejection before
any prior mutation) and the multi-replica test used service/repository stacks
rather than HTTP instances, with a second engine that lost the fixture search
path.

**fix:** The rollback test now uses asymmetric limits (`account` 3, `source` 2,
evaluated in stable key order) so one rule mutates before the later rule
rejects, proving rollback undoes the consumption
(`tests/integration/test_limiter_atomicity.py`). The multi-replica test now
runs two independent ASGI HTTP clients, each with its own engine/session stack
bound to the same schema (`search_path` preserved on both engines), against
shared PostgreSQL (`tests/integration/test_limiter_multireplica.py`). It sends
invalid credential attempts over HTTP and verifies the combined 401s cannot
exceed the shared account bound.

#### 8. Secret provisioning documentation omits limiter secret commands — FIXED

**verification-01:** The limiter HMAC and assertion secrets were listed but
absent from the manual population commands.

**fix:** Added `gcloud secrets versions add` commands (and an `openssl rand`
generation example) for both limiter secrets to
`docs/deployment/external-secrets.md`. Added a deploy workflow step
(`Verify limiter HMAC and assertion secrets are projected before rollout`) that
fails before rollout when either projected value is absent from the runtime
Secret.

#### 9. Checked task 7.6 lacks a reproducible backend verification result — FIXED

**verification-01:** Backend pytest could not start under Python 3.10
(`datetime.UTC` missing); PostgreSQL suites were not executed; Playwright had
no limiter rejection journey.

**fix:** All backend suites were executed under Python 3.12 (project minimum)
via the `fotosintesis-test` Docker image with exact result counts; PostgreSQL
integration tests ran against `pgvector/pgvector:pg16`. Added the auth E2E 429
journeys (header propagation, countdown, disabled resubmission, neutral
recovery) in `frontend/e2e/auth-rate-limit.spec.ts`. Exact counts and commands
are recorded in "Verification Commands" below.

## Requirement Coverage

All 42 scenarios from verification-01 now pass or are covered by direct tests:

- **Fully covered:** trusted GKE source identity, distributed authjs_post
  enforcement, strictly fail-closed storage behavior, retention-aware cleanup,
  token-derived recovery-confirmation account keys, single response contract
  with documented `Retry-After`, bounded error-code retry propagation, forms
  using the server duration, allowlisted internal headers, string ConfigMap
  values, Cloud SQL-connected cleanup, complete secret provisioning docs, and
  deploy-gated limiter secret availability.
- **Multi-instance evidence:** HTTP-level two-instance ASGI verification against
  shared PostgreSQL with preserved search paths.
- **Privacy lifecycle:** opaque persisted digests (including recovery tokens),
  closed metric labels, no raw forwarding headers crossing the boundary, and
  expanded assertions across rows, responses, logs, and metrics.

## Verification Commands

All backend commands ran under Python 3.12 in the `fotosintesis-test:latest`
Docker image (the project requires `python >= 3.12`); the local interpreter is
3.10 and cannot run `datetime.UTC`.

| Command | Result |
|---|---|
| `openspec validate rate-limit-authentication-flows --strict` | Passed |
| `git diff --check` | Passed |
| `ruff check app tests` (Python 3.12) | Passed |
| `pytest tests/ --ignore=tests/integration` (Python 3.12) | 894 passed |
| `pytest tests/integration/...` (pgvector/pgvector:pg16, `TEST_DATABASE_URL` on 127.0.0.1:5433) | 234 passed (full suite); 40 passed (limiter/migration/observability focus) |
| `pytest tests/deployment/` | 83 passed |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm test` | 332 passed |
| `pnpm openapi:check` | Passed |
| `pnpm build` | Passed |
| `pnpm test:e2e:auth` | 10 passed (7 original + 3 rate-limit journeys) |
| `pnpm smoke:auth-failclosed` | Passed |
| Rendered ConfigMap type inspection (dev + prod) | All 34 values are strings |
| Kubernetes client dry run | Blocked by expired GKE credentials; offline YAML structure validated in deployment tests |

## Verification Comparison

| Report | Critical | Warnings | Supported tasks | Assessment |
|---|---:|---:|---:|---|
| `verification-01.md` | 5 | 9 | 18/33 | Not ready to archive |
| `verification-02.md` | 0 | 0 | 33/33 | Ready to archive |

Every critical finding and every warning from `verification-01.md` is
resolved by runtime behavior plus focused negative tests, not by configuration
or documentation alone. No finding regressed.

## Final Assessment

The implementation now matches the security design across the trusted source
boundary, distributed enforcement, bounded failure behavior, retry and response
contracts, recovery confirmation, and deployable shared-state cleanup. All
checked tasks are supported by runtime call sites and failure-path tests, and
the full verification matrix (backend unit + PostgreSQL integration +
deployment + frontend + E2E) passes under Python 3.12. The change is ready to
archive.
