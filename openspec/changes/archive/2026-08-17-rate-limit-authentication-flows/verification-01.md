# Verification Report: rate-limit-authentication-flows

Verified on 2026-08-14 against the change proposal, design, five delta specifications, 33 checked tasks, implementation, tests, generated contracts, and rendered production manifests.

## Summary

| Dimension | Status |
|---|---|
| Completeness | 33/33 tasks marked complete; 18 credibly supported and 15 materially incomplete or unsupported |
| Correctness | 4/18 requirements fully covered, 11 partially covered or divergent, 3 not implemented; 42 scenarios reviewed |
| Coherence | Core PostgreSQL/HMAC architecture is present, but critical trust-boundary, fallback, Auth.js, retry, and deployment decisions are not followed |
| Archive readiness | Not ready; 5 critical and 9 warning findings |

## Critical Findings

### 1. Production source identity selects the load balancer address

`extractTrustedClientAddress()` selects the final `X-Forwarded-For` entry under the production `gke-last` policy (`frontend/src/lib/server/source-identity.ts:25`, `frontend/src/lib/server/source-identity.ts:55`). Google external Application Load Balancers append the client and load-balancer addresses, so the final entry is the load balancer rather than the originating client. Production enables this policy (`deploy/k8s/prod/values.env.example:42`), and tests and documentation encode the same assumption (`frontend/src/lib/server/source-identity.test.ts:41`, `docs/deployment/authentication-abuse-limits.md:13`). This can collapse public users into one low-threshold source bucket and create a global authentication denial of service.

Recommendation: implement the exact verified GKE forwarding-chain contract, configure trusted proxy hop count or position explicitly, reject malformed chains conservatively, and add tests using representative GKE headers plus attacker-prepended entries. Revalidate against current Google Cloud documentation before enabling production enforcement; Context7 and the official page were unreachable during this verification.

### 2. Relevant Auth.js POST operations are not rate limited

The Auth.js route exports its raw POST handler (`frontend/src/app/api/auth/[...nextauth]/route.ts:1`) and no runtime code evaluates `EndpointCategory.authjs_post`. The category exists only in backend policy/configuration (`backend/app/limiter/policy.py:31`). This contradicts the Auth.js POST requirement and checked task 5.1.

Recommendation: wrap the relevant unauthenticated Auth.js POST operations at the Next.js server boundary, enforce the configured distributed source policy before Auth.js work, preserve session reads and logout semantics, and test allowed, rejected, and storage-failure outcomes.

### 3. `bounded_fallback` is unbounded fail-open behavior

Every limiter-storage exception configured as `bounded_fallback` returns `allowed` (`backend/app/limiter/service.py:116`) without a local counter, window, lock, or admission bound. The comment claiming one request per process per window is not implemented. This violates the storage-failure requirement and checked task 4.5.

Recommendation: remove `bounded_fallback` until a concurrency-safe bounded implementation exists, or implement and test the documented per-process/window bound. Keep production categories fail closed.

### 4. Rendered limiter ConfigMap values are not strings

Limiter boolean and numeric substitutions are unquoted in `deploy/k8s/base/20-config.yaml:37`. Rendering production values produces YAML booleans and integers for `AUTH_LIMITER_ENABLED`, key version, retry maximum, retention, and cleanup batch size. `ConfigMap.data` requires string values. The deployment test incorrectly expects a YAML boolean (`backend/tests/deployment/test_render_limiter.py:114`).

Recommendation: quote every ConfigMap substitution, update deployment tests to require strings, and validate rendered manifests against Kubernetes schemas in CI.

### 5. The cleanup CronJob lacks Cloud SQL connectivity

The cleanup job receives `DATABASE_URL` but has no Cloud SQL Auth Proxy sidecar (`deploy/k8s/base/56-limiter-cleanup.yaml:27`). Backend and migration workloads use a proxy for the same database deployment model (`deploy/k8s/base/30-backend.yaml:216`, `deploy/k8s/base/50-migrations.yaml:23`). With the normal localhost proxy URL, limiter cleanup cannot connect.

Recommendation: add the same reviewed Cloud SQL Auth Proxy connectivity and shutdown behavior used by migration/backend workloads, then test the rendered pod structure and execute a cleanup smoke test.

## Warnings

### 1. Forms ignore authoritative `Retry-After`

The client retains parsed retry metadata (`frontend/src/lib/api/client.ts:61`), but registration and recovery always block for 60 seconds (`frontend/src/components/auth/RegisterForm.tsx:13`, `frontend/src/components/auth/RecoveryForm.tsx:12`). Auth.js discards the parsed credential retry duration (`frontend/auth.ts:82`), and login also uses 60 seconds (`frontend/src/components/auth/LoginForm.tsx:14`). This permits premature retry for longer limits and overblocks shorter limits.

Recommendation: propagate bounded retry seconds through Auth.js and `ApiClientError`, calculate each deadline from that value, display generic timing, and test short and maximum delays.

### 2. Authentication route handlers propagate raw client headers

Registration and recovery clone all request headers and remove only internal limiter headers (`frontend/src/app/api/auth/register/route.ts:12`, `frontend/src/app/api/auth/recovery/request/route.ts:12`). Raw forwarding headers, cookies, and unrelated client headers continue to FastAPI, contrary to the design decision to forward only required headers and an opaque authenticated source assertion.

Recommendation: construct an allowlisted internal header set containing content type and the generated source assertion only, and add tests proving forwarding and internal limiter headers supplied by clients are removed.

### 3. Recovery confirmation lacks the documented account dimension

Documentation promises source and account limits for recovery confirmation (`docs/authentication-abuse-limits.md:40`), but production policy sets the account profile to `null`, and the endpoint supplies no account identifier (`backend/app/api/auth.py:161`).

Recommendation: either implement a token-derived keyed account dimension that does not reveal token state, or revise the specification and documentation before `complete-password-recovery` consumes this boundary.

### 4. Retention configuration is unused

`AUTH_LIMITER_RETENTION_SECONDS` is validated and deployed, but cleanup deletes rows as soon as `window_end < now` (`backend/app/limiter/repository.py:141`). This contradicts the configured retention lifecycle and checked task 2.5.

Recommendation: apply retention to the cleanup cutoff and add boundary tests proving active and retained windows survive while older rows are removed.

### 5. Generated error contracts do not match runtime responses

`RateLimitResponse` requires `retry_after_seconds` in the JSON schema (`backend/app/auth/schemas.py:67`), but runtime `HTTPException` bodies contain only `detail`; retry data is header-only (`backend/app/limiter/http.py:19`). Generated responses also omit a typed `Retry-After` header.

Recommendation: make runtime and OpenAPI agree by returning the declared body and response header or by changing the schema to the actual contract, then regenerate and test the client.

### 6. Retry calculation can emit zero during an active window

Remaining fixed-window time is floored with `int()` (`backend/app/limiter/repository.py:78`), so an active rejected window can return `Retry-After: 0`. Tests currently accept this behavior.

Recommendation: round positive remaining time up and enforce a minimum of one second for an active rejection.

### 7. Multi-rule and multi-replica tests overstate their evidence

The rollback test exhausts equal source and account limits, so sorted account rejection occurs before a prior mutation and does not prove rollback after partial consumption (`backend/tests/integration/test_limiter_atomicity.py:104`). The multi-replica test constructs two service/repository stacks rather than sending invalid credentials through two application instances (`backend/tests/integration/test_limiter_multireplica.py:69`), and its second engine does not preserve the fixture search path.

Recommendation: use asymmetric rules to force one successful mutation before a later rejection, retain the test schema on every engine, and add an HTTP-level two-instance acceptance test.

### 8. Secret provisioning documentation omits limiter secret commands

The limiter HMAC and assertion secrets are listed (`docs/deployment/external-secrets.md:15`) but absent from the manual population commands (`docs/deployment/external-secrets.md:48`). Following the documented procedure leaves required runtime secrets without versions.

Recommendation: add secure population examples for both limiter secrets and deployment validation that fails before rollout when either projected value is absent.

### 9. Checked task 7.6 lacks a reproducible backend verification result

Backend lint passes, but backend pytest cannot start in this workspace because Python 3.10 lacks `datetime.UTC`; the project requires Python 3.12 (`backend/pyproject.toml:9`). PostgreSQL migration/concurrency suites therefore were not executed in this verification. Existing Playwright auth journeys pass but contain no limiter rejection journey.

Recommendation: rerun all backend and PostgreSQL suites under Python 3.12, add the missing rate-limit Playwright path, and record exact counts before treating task 7.6 as complete.

## Requirement Coverage

### Fully covered

- Shared persistent limiter state and atomic database updates.
- Account-specific relaxation after successful authentication while source rows remain structurally separate.
- Closed-cardinality limiter metric labels.
- Optional edge protection documented as complementary to application limits.

### Partially covered or divergent

- Distributed authentication policy: backend categories are enforced, but Auth.js POST is absent and multi-replica evidence is service-level.
- Source/account keys: HMAC storage exists, but the production source address position is unsafe and recovery confirmation lacks an account key.
- Enumeration-resistant rejection: recovery bodies are neutral, but typed and retry contracts diverge.
- Storage-failure behavior: fail-closed paths exist, but bounded fallback is unbounded.
- Registration, login, and recovery initiation: backend admission exists, but frontend retry behavior and trusted source extraction diverge.
- Authentication forms: disabling exists, but the authoritative retry duration is ignored.
- Persistent cleanup: batching and expiry indexing exist, but retention and deployed connectivity are incomplete.
- Limiter verification: substantial unit coverage exists, but concurrency, real multi-instance, spoofing, privacy, and E2E evidence are incomplete.
- Deployment contract: configuration and secrets are represented, but rendered ConfigMap types, cleanup connectivity, and secret instructions are incomplete.
- Privacy lifecycle: opaque persisted keys and bounded metrics exist, but raw forwarding headers continue across the internal boundary.
- Recovery confirmation policy: source enforcement exists, but the documented account-aware boundary does not.

### Not implemented

- Correct trusted GKE source identity and deployment verification.
- Relevant Auth.js POST abuse enforcement.
- Strictly bounded local fallback on limiter-storage failure.

## Verification Commands

| Command | Result |
|---|---|
| `openspec validate rate-limit-authentication-flows --strict` | Passed |
| `git diff --check` | Passed |
| Focused Ruff check for limiter implementation/tests | Passed |
| Focused frontend limiter Vitest suite | 80 passed |
| `pnpm test` | 307 passed |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm openapi:check` | Passed, despite semantic runtime/schema mismatch noted above |
| `pnpm build` | Passed with pre-existing Sass/autoprefixer and ESLint-plugin warnings |
| `pnpm test:e2e:auth` | 7 passed; no limiter rejection journey exists |
| Focused backend pytest | Blocked before collection: local Python 3.10, project requires Python 3.12 |
| Production manifest render | Passed |
| Kubernetes client dry run | Blocked by expired GKE/gcloud credentials and unavailable network |
| Independent rendered ConfigMap type inspection | Failed: limiter boolean and numeric data values are non-string YAML types |

## Verification Comparison

This is the first numbered verification for this change. No `verification-00.md` or earlier change-local report exists in the working tree or Git history, so there is no prior result to compare without fabricating a baseline.

| Report | Critical | Warnings | Supported tasks | Assessment |
|---|---:|---:|---:|---|
| `verification-01.md` | 5 | 9 | 18/33 | Not ready to archive |

The next verification should be `verification-02.md` and compare remediation of each finding against this baseline.

## Final Assessment

Five critical issues must be fixed before archive. The most urgent is the production trusted-source calculation because it can group all users behind the load balancer into one limiter identity. The checked task list overstates completion; the implementation is not coherent with the security design until trusted identity, Auth.js POST enforcement, bounded failure behavior, and deployable shared-state cleanup are corrected.
