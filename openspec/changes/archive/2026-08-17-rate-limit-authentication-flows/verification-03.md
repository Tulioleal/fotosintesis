# Verification Report: rate-limit-authentication-flows

Verified on 2026-08-17 against the proposal, design, five delta specifications,
33 checked tasks, current implementation, tests, deployment workflow, generated
contracts, and `verification-02.md`.

## Summary

| Dimension | Status |
|---|---|
| Completeness | 33/33 tasks marked complete; 24 fully supported and 9 partial or unsupported |
| Correctness | 8/18 requirements fully covered and 10 partially covered; 42 scenarios reviewed |
| Coherence | Major verification-01 fixes remain, but production configuration, deployment cleanup, failure classification, and verification evidence still diverge from the design |
| Archive readiness | Not ready; 4 critical findings and 8 warnings |

## Critical Findings

### 1. The cleanup CronJob is never applied

The deployment workflow validates only backend, frontend, migrations, and
worker manifests (`.github/workflows/deploy.yml:825-833`) and later applies
migrations, worker, backend, frontend, certificate, and ingress
(`.github/workflows/deploy.yml:845-958`). It never validates or applies
`56-limiter-cleanup.yaml`. The rendered CronJob and Cloud SQL proxy are correct,
but no scheduled cleanup exists in deployed environments.

Recommendation: include `56-limiter-cleanup.yaml` in server-side validation and
apply it after migrations, then add workflow/static tests proving the CronJob is
part of the deployment path.

### 2. Production can start with the limiter disabled

`AUTH_LIMITER_ENABLED` defaults to false (`backend/app/core/settings.py:106`),
and startup accepts that value even when `APP_ENV=prod`. Disabled mode returns
before enforcement or metrics (`backend/app/limiter/service.py:82-84`). A
missing or incorrect production setting can therefore remove the complete
authentication abuse boundary without failing startup.

Recommendation: reject `APP_ENV=prod` when the limiter is disabled and add a
startup test for the invariant. Keep explicit disabling available only outside
production.

### 3. Required account-aware policies remain optional

Every endpoint policy permits `account=None`
(`backend/app/limiter/policy.py:76-81`), settings accept null account profiles
(`backend/app/core/settings.py:170-180`), and the limiter silently omits the
account key (`backend/app/limiter/service.py:63-67`). Credential verification,
recovery initiation, and recovery confirmation can therefore start in a
source-only configuration despite normative account-aware requirements.

Recommendation: validate non-null account profiles for those three categories
when enforcement is enabled and add negative startup tests.

### 4. The two-instance acceptance test uses one global application override

Both clients use the module-level FastAPI `app`, and `_make_client()` replaces
the global `get_async_session` dependency override
(`backend/tests/integration/test_limiter_multireplica.py:66-86`). Creating the
second client overwrites the first client's session stack before requests run
(`backend/tests/integration/test_limiter_multireplica.py:133-151`). The test
proves shared enforcement through one effective application/session override,
not two independent instances as required by task 7.4.

Recommendation: create two independent FastAPI application objects with
instance-local dependency overrides and engines, or run two real processes
against the same PostgreSQL schema.

## Warnings

### 1. A valid configuration can still emit `Retry-After: 0`

The maximum retry setting and policy permit zero
(`backend/app/core/settings.py:116-118`, `backend/app/limiter/policy.py:92-95`).
Repository logic first enforces one second and then clamps back to zero
(`backend/app/limiter/repository.py:80-87`), contradicting the OpenAPI minimum.

Recommendation: require `AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS >= 1` and test
the minimum configuration boundary.

### 2. Auth.js storage failures are shown as rate limiting

The Auth.js wrapper maps backend 503 to the bare rate-limit code
(`frontend/src/app/api/auth/[...nextauth]/route.ts:56-59`). `LoginForm` treats
that code as excessive attempts and starts a 60-second limit
(`frontend/src/components/auth/LoginForm.tsx:48-54`). The declared
`temporarily_unavailable` code is unused.

Recommendation: propagate a distinct unavailable code through both Auth.js
paths and show generic temporary-unavailability feedback without claiming a
limit was reached.

### 3. Storage-failure retry timing ignores policy bounds

`raise_storage_failure()` always emits 60 seconds
(`backend/app/limiter/http.py:42-52`) instead of using the bounded retry value
already carried by `AdmissionOutcome`.

Recommendation: pass the outcome into the storage-failure response and clamp
its header through the same policy contract as 429 responses.

### 4. Malformed recovery confirmations bypass limiter admission

Pydantic rejects short tokens before the endpoint limiter call
(`backend/app/auth/schemas.py:78-80`, `backend/app/api/auth.py:173-190`). Tests
expect 422 for malformed input while token-shaped requests return 200 or 429.
This does not satisfy the design statement that malformed-but-routable auth
submissions consume the source boundary, and it overstates malformed-token
neutrality in `verification-02.md`.

Recommendation: enforce the source boundary before body validation or revise
the design/specification explicitly; add a test that proves malformed request
flooding is bounded.

### 5. Deployment-level spoofing remains unverified

Source extraction unit tests correctly model the GKE two-entry suffix, but the
Playwright environment does not configure trusted hops or limiter secrets
(`frontend/playwright.auth.config.ts:21-41`), and its backend stub does not
inspect the source assertion. No deployment-level test injects spoofed
forwarding entries and observes the resulting limiter identity.

Recommendation: add an integration or deployment test that traverses the
Next.js boundary with representative and spoofed GKE forwarding chains.

### 6. Verification-02 overstates Auth.js credential-path evidence

The E2E limiter stub rejects `/auth/admit/authjs_post` before Auth.js reaches
the credentials provider. It proves wrapper rejection and form behavior, but
not propagation of a backend `/auth/credentials/verify` 429 through the real
`CredentialsRateLimited` path.

Recommendation: add a stub mode that admits `authjs_post` and rate-limits only
credential verification, then verify the real Auth.js error-code journey.

### 7. Privacy and rollout documentation evidence is incomplete

Privacy tests do not check an actual digest key across logs and metrics, while
token checks do not cover all output surfaces. Operations also document a
disabled report-only rollout, but disabled mode emits no limiter outcomes.

Recommendation: expand cross-surface privacy sentinels and either implement a
real report-only mode or remove that rollout instruction.

### 8. Full verification evidence is not currently reproducible

`verification-02.md` references a `fotosintesis-test:latest` image and abbreviated
integration commands. That image is absent locally, Python 3.12 backend commands
cannot be reproduced from the recorded report alone, and fresh auth E2E timed
out after its web servers became unhealthy. The frontend production build passes
when run separately.

Recommendation: record exact Docker build/run commands or pin CI run URLs,
versions, environment, and test files. Keep task 7.6 incomplete until the full
matrix is reproducible.

## Re-Proved Fixes From Verification-02

- GKE source extraction now selects the client from the trusted two-entry
  suffix and rejects malformed or short chains.
- Internal frontend requests use an allowlist and do not propagate raw client
  forwarding headers or cookies.
- Auth.js POST has a real backend shared-state admission route and wrapper.
- Limiter storage exceptions fail closed; the unbounded fallback was removed.
- Rendered ConfigMap values are strings.
- The cleanup manifest contains the reviewed Cloud SQL proxy sidecar pattern,
  although the workflow does not deploy it.
- Recovery confirmation supplies a token-derived opaque account key in the
  checked-in policy and endpoint.
- Retention-aware cleanup, OpenAPI body/header alignment, retry rounding for
  positive maxima, asymmetric transaction rollback, secret provisioning docs,
  and frontend server-duration countdowns remain implemented.

## Fresh Verification Commands

| Command | Result |
|---|---|
| `openspec validate rate-limit-authentication-flows --strict` | Passed |
| `git diff --check` | Passed |
| `pnpm lint` | Passed |
| `pnpm typecheck` | Passed |
| `pnpm openapi:check` | Passed |
| `pnpm test` | 332 passed |
| `pnpm build` | Passed when rerun separately; existing Sass/autoprefixer and ESLint plugin warnings remain |
| `pnpm test:e2e:auth` | Inconclusive: timed out after web-server instability; orphaned verification processes were terminated |
| Focused Python 3.12 backend tests from independent audits | Limiter/OpenAPI/deployment and 8 PostgreSQL tests passed |
| Full backend Python 3.12 matrix from verification-02 | Not reproducible from the recorded local image/commands |
| Kubernetes server dry run and live cleanup | Not run; requires active cluster credentials |

## Comparison With Verification-02

| Area | verification-02 | verification-03 |
|---|---|---|
| Critical findings | 0 | 4 |
| Warnings | 0 | 8 |
| Fully supported tasks | 33/33 | 24/33 |
| Assessment | Ready to archive | Not ready to archive |

This comparison does not indicate that the verification-01 remediations were
reverted. Most remain valid. The difference is that verification-03 followed
runtime configuration and deployment wiring beyond rendered files and inspected
whether tests actually created the independent boundaries they claimed. It
found false closure in verification-02 around production-safe startup,
deployment of cleanup, multi-instance evidence, and complete failure-path
coverage.

## Final Assessment

Four critical issues must be resolved before archive. The most immediate
production defect is that the cleanup CronJob is never applied. The limiter must
also be mandatory in production, required account-aware categories must reject
unsafe profiles, and multi-replica acceptance must use genuinely independent
application instances. After remediation, create `verification-04.md` and
compare every finding in this report with reproducible command evidence.
