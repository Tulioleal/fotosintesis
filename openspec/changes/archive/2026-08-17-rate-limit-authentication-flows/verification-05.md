# Verification Report: rate-limit-authentication-flows (Independent Recheck)

Verified on 2026-08-17 against the proposal, design, five delta
specifications, 42 checked tasks, current implementation and tests, deployment
artifacts, and `verification-04.md`.

## Summary

| Dimension | Status |
|---|---|
| Completeness | 42/42 tasks checked; all 18 requirements have implementation evidence |
| Correctness | 43/44 scenarios have evidence matching the literal scenario scope; one deployment scenario has contract-level evidence only |
| Coherence | Core design is followed, with one malformed-request divergence and one verification-order defect |
| Archive readiness | Conditional: 0 criticals, 3 warnings, 2 suggestions |

The five delta specifications contain 18 requirements and 44 scenarios: 6/15
in `authentication-abuse-controls`, 4/14 in `authentication-home`, 2/3 in
`persistent-auth-storage`, 2/5 in `secure-auth-session-boundary`, and 4/7 in
`testing-deployment`.

## Critical

None.

## Warnings

### 1. Malformed non-recovery submissions do not consume the documented source boundary

The design says malformed-but-routable authentication submissions consume the
source boundary (`design.md:51-55`). FastAPI validates the request models before
entering the endpoint (`backend/app/auth/schemas.py:14-59`), while limiter
admission occurs inside the registration, credential-verification, and recovery
endpoints (`backend/app/api/auth.py:80-89`, `backend/app/api/auth.py:98-110`,
`backend/app/api/auth.py:151-162`). Invalid bodies therefore return `422` without
consuming limiter state.

Recovery confirmation has an explicit schema-validation exception in the design
and specification; the other authentication operations do not. This does not
permit password hashing or token writes, but it diverges from the documented
source-boundary claim.

Recommendation: either enforce a source-only admission boundary before body
validation for the affected routes, or narrow `design.md:55` to the payloads
that can reach endpoint admission and add a regression test for the chosen
contract.

### 2. Forwarding-header spoofing evidence is not deployment-path evidence

The deployment scenario says deployment verification sends spoofed forwarding
headers (`specs/testing-deployment/spec.md:37-44`). Current tests thoroughly
cover trusted-suffix extraction and route behavior
(`frontend/src/lib/server/source-identity.test.ts:43-175`,
`frontend/src/app/api/auth/register/route.test.ts:59-163`) and backend assertion
rejection (`backend/tests/test_auth_limiter.py:413-429`,
`backend/tests/test_auth_limiter.py:666-692`). Operational documentation
correctly identifies this as contract-level integration evidence rather than a
live GKE test (`docs/deployment/authentication-abuse-limits.md:41-62`).

Recommendation: align `specs/testing-deployment/spec.md` with the accepted
contract-level scope, or add a deployed ingress-path spoofing test before
claiming the literal scenario is complete.

### 3. The recorded frontend gate order is not reproducible

`verification-04.md:72-81` records `pnpm build`, then `pnpm test:e2e:auth`, then
`pnpm smoke:auth-failclosed` as a passing sequence. Repeating that sequence
passes the build and all 14 journeys, but the smoke fails because Playwright's
development server removes the production `.next/BUILD_ID`; `next start` then
reports that no production build exists. Running `pnpm build` immediately before
the smoke passes and verifies the expected fail-closed redirect.

Recommendation: run the smoke immediately after `pnpm build`, before the E2E
development server, or give build, E2E, and smoke isolated Next.js output
directories. Update task 7.6 evidence and the reproducible command order.

## Suggestions

### 1. Narrow task 7.5 response wording

Task 7.5 says responses contain no email or raw account identifier
(`tasks.md:52`), although successful authentication responses legitimately
contain public user fields (`backend/app/api/auth.py:41-47`,
`backend/app/api/auth.py:90-94`). The privacy tests correctly apply the stronger
assertion to limiter rejection and failure surfaces
(`backend/tests/test_auth_limiter_privacy.py:297-320`).

Recommendation: change task 7.5 to say "limiter rejection and failure
responses" so the checked task matches its evidence.

### 2. Keep the live-cloud limitation explicit

No Kubernetes server-side dry-run against a cluster, live GKE forwarding test,
or Cloud Armor validation was run. Continue treating these as operational
follow-up rather than completed product evidence.

## Verification-04 Comparison

| Area | Verification-04 | Verification-05 recheck |
|---|---|---|
| Verification-03 critical remediations | All four fixed | Confirmed; no regression found |
| Verification-03 warnings | All fixed or accepted | Confirmed for the implemented remediation scope |
| Requirements and scenarios | Uncounted, described as fully covered | 18 requirements and 44 scenarios; one scenario is only partially evidenced at its literal deployment scope |
| Malformed request boundary | No issue reported | New warning: non-recovery `422` paths bypass admission despite `design.md:55` |
| Frontend matrix | Reported fully reproducible | New warning: the recorded build/E2E/smoke order fails; each gate passes with build immediately before smoke |
| Archive recommendation | Ready to archive | Conditionally ready after warning acceptance or correction |

The previous remediation remains effective: production requires limiter
enforcement, required account profiles are validated, retry values remain
positive and policy-bounded, Auth.js distinguishes limited from unavailable,
cleanup is deployed, the multi-instance test uses independent application
boundaries, and privacy tests exercise actual digest values.

## Verification Matrix

### Passed

```text
OpenSpec strict validation                         passed
git diff --check                                  passed
Backend non-integration tests, Python 3.12        919 passed
PostgreSQL integration tests, fresh database      234 passed
Limiter/migration integration subset              8 passed (within 234)
Deployment tests                                  85 passed (within 919)
Frontend lint                                     passed
Frontend typecheck                                passed
Frontend unit/component tests                     349 passed
Generated OpenAPI contract check                  passed
Frontend production build                         passed with pre-existing warnings
Authentication Playwright journeys                14 passed
Fail-closed production smoke after fresh build    passed
```

The PostgreSQL suite was rerun against a newly created empty database to avoid
contamination from the persistent compose volume. The full workspace was mounted
for deployment tests so repository-relative deployment paths resolved correctly.

### Not Reproduced

The exact Docker Compose lint command could not install the pinned development
dependencies because the container could not resolve `files.pythonhosted.org`.
The available `fotosintesis-test:latest` image contains Ruff 0.16.2, outside the
project's `ruff>=0.15.22,<0.16` pin, so its 0.16-only lint findings are not a
valid project lint result. Backend tests still ran under Python 3.12.13 in that
image. Ruff 0.15.22 was not available offline and lint is therefore not claimed
as independently reproduced in this report.

## Final Assessment

No critical implementation issue was found. Distributed enforcement, atomic
shared state, bounded failure behavior, retry propagation, privacy controls,
cleanup, deployment rendering, and all verification-03 remediations have direct
code and passing test evidence.

Three warnings remain. Before archive, resolve or explicitly accept the
malformed-request design divergence and the contract-level proxy-test scope, and
correct the frontend verification order. With those qualifications recorded,
the change is ready for archive with noted improvements; it is not supported by
the unconditional reproducibility claim made in `verification-04.md`.
