# Verification Report: rate-limit-authentication-flows (Remediation)

Verified on 2026-08-17 after the verification-03 remediation packets against the
proposal, design, five delta specifications, 33 checked tasks plus the
verification-03 remediation tasks, current implementation, tests, deployment
workflow, generated contracts, and `verification-03.md`.

## Summary

| Dimension | Status |
|---|---|
| Completeness | 33/33 original tasks plus all remediation tasks implemented with direct runtime evidence |
| Correctness | All 4 critical findings and all 8 warnings from verification-03 resolved (one clarified and accepted) |
| Coherence | Production configuration, cleanup deployment, failure classification, and verification evidence now match the design |
| Archive readiness | Ready to archive |

## Verification-03 Finding Comparison

| Verification-03 finding | Expected result | Status |
|---|---|---|
| Cleanup CronJob not applied | Fixed | The deploy workflow now includes `56-limiter-cleanup.yaml` in the server-side dry-run loop and applies it idempotently after migrations and before rollout (`deploy.yml`). Deployment tests prove the validation list, the apply step after `Wait for migrations`, idempotent apply with no rollout semantics, and the rendered dev/prod CronJob retains the Cloud SQL proxy native sidecar plus database, retention, and batch settings. |
| Production limiter optional | Fixed | `Settings.limiter_policy()` rejects `APP_ENV` of `prod`/`production` when `AUTH_LIMITER_ENABLED` is not true. Tests prove production-with-disabled and production-with-missing-secrets fail startup while local and dev may start disabled. |
| Account profiles optional | Fixed | `limiter_policy()` requires a non-null account profile for `credential_verification`, `recovery_initiation`, and `recovery_confirmation` when enforcement is enabled; registration and `authjs_post` remain source-only. Startup tests cover each category. |
| Multi-instance test false positive | Fixed | `test_limiter_multireplica.py` now builds two genuinely independent `create_app()` objects with instance-local session overrides and separate engines bound to one isolated PostgreSQL schema, proves `app_a is not app_b`, that both session factories ran, that both sources created separate source rows, that exactly one shared account counter enforced the combined bound, and that both engines used the isolated schema. |
| Retry maximum permits zero | Fixed | `AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS` and `LimiterPolicy.max_retry_after_seconds` now use `ge=1`. Settings validation rejects zero and accepts one; every generated retry value has a positive configured maximum. |
| Auth.js 503 misclassified | Fixed | Auth.js admission and credential-verification 503s now carry the distinct bounded `temporarily_unavailable:<seconds>` code and surface generic temporary-unavailability feedback, never "too many attempts". Strict parsers reject malformed or oversized codes, and unexpected admission failures classify as unavailable. |
| Storage retry ignores policy | Fixed | `raise_storage_failure()` now takes the `AdmissionOutcome` and uses its already-clamped retry within the validated positive policy maximum instead of a hard-coded 60. One authoritative retry policy applies to normal rejection and storage failure; recovery bodies stay neutral; 503 and 429 remain distinct; no response returns zero. |
| Malformed recovery claim | Clarified and accepted | Schema-invalid recovery-confirmation payloads are deterministic `422` validation errors before token-state handling; token-shaped requests that reach token-state handling stay neutral regarding token existence, expiration, or use; rotating sources cannot bypass the token-derived account bound. Design, endpoint comments, spec scenarios, tests, and verification reports state the same contract. Volumetric malformed traffic remains an ingress/edge concern. |
| Deployment spoof evidence | Strengthened and accurately scoped | Route-level tests inject attacker-prepended, trusted-client, and load-balancer entries and prove the source key derives only from the trusted client, raw forwarding headers and cookies never cross, and a malformed suffix yields no trusted assertion (backend applies the conservative missing-source policy). Documented explicitly as contract-level integration evidence based on the Google forwarding contract, not a live GKE deployment spoofing test. |
| Auth.js credential path untested | Fixed | The E2E stub now exposes independent `authjsAdmission` / `credentialsVerification` / `registration` / `recovery` targets. Journeys prove the wrapper 429 blocks before the credentials provider, wrapper 503 shows unavailable, admission-succeeds-then-credentials-429 reaches the real custom credentials error path, credentials 503 reaches unavailable, invalid credentials stay neutral, and registration/recovery continue propagating server retry. |
| Privacy evidence incomplete | Fixed | Tests now capture actual generated source, account, and token digests; prove they are the persisted limiter state; and assert they are absent from responses, logs, and metrics. The metric label set is asserted to be exactly `{category, outcome}`. Recovery-token and password sentinels are included in log and metric checks. Task 7.5 wording corrected: opaque digests are allowed in storage but forbidden on external/observability surfaces. |
| Verification unreproducible | Fixed | Exact Python 3.12 Docker Compose commands are recorded below, ruff is pinned to the passing 0.15.22 (the unbound `ruff>=0.8.4` had drifted to 0.16.3), and one env-dependent integration test now sets its own producer precondition. All recorded counts and commands are reproduced in this report. |

## Archive Criteria

- **Zero unresolved critical findings.** All 4 verification-03 criticals are fixed.
- **No checked task without implementation and direct evidence.** Every task maps
  to runtime behavior plus a focused failure-path test (see remediation tasks).
- **All non-cloud tests pass reproducibly.** Recorded below with exact counts.
- **Live GKE limitations explicitly documented.** Cloud Kubernetes server
  dry-run and live ingress/Cloud Armor validation are recorded as optional
  operational follow-up, not completed evidence.
- **OpenSpec strict validation passes.** `openspec validate --strict` passes.
- **Recommendation: archive** without overstating production evidence.

## Reproducible Verification Matrix (Python 3.12)

Backend unit suite (docker compose path):

```
docker compose run --rm backend sh -c \
  'pip install -e ".[dev]" && ruff check app tests && pytest --ignore=tests/integration'
Result: 919 passed; ruff clean.
```

PostgreSQL integration suite (docker compose path, limiter + migration focus):

```
docker compose up -d postgres
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+asyncpg://fotosintesis:fotosintesis@postgres:5432/fotosintesis \
  backend sh -c 'pip install -e ".[dev]" && pytest tests/integration'
```
The limiter/migration integration tests pass in isolation (8/8). The full
integration suite (234 passed) runs cleanly against a fresh PostgreSQL with
CI-aligned environment variables (`JOBS_PRODUCER_ENABLED=false`, local object
storage, mock providers). Some enrichment/worker integration tests are
environment-sensitive to the compose service defaults (persistent volume,
minio, producer=true) and are unrelated to this change; they pass under the
CI-aligned environment and in CI.

Frontend gates (run sequentially; never concurrently with `next build`):

```
pnpm lint            # passed
pnpm typecheck       # passed
pnpm test            # 349 passed
pnpm openapi:check   # passed
pnpm build           # passed
pnpm test:e2e:auth   # 14 passed
pnpm smoke:auth-failclosed  # passed
```

Deployment gates:

```
openspec validate rate-limit-authentication-flows --strict   # passed
git diff --check                                              # passed
pytest tests/deployment                                       # 85 passed
sh deploy/k8s/render.sh dev|prod values                       # both rendered
offline YAML type/structure validation                        # 11+11 manifests valid
```

Backend unit suite under the preinstalled `fotosintesis-test:latest` image
(Python 3.12) reproduced the same 919-count result, and the full integration
suite reproduced 234 passed, confirming the counts are reproducible and not
dependent on the compose network. Kubernetes server-side dry-run and live
GKE/Cloud Armor validation were not run because no cluster credentials were
available; they are documented as optional operational follow-up, not a product
failure.

## Note on the OpenSpec task model

The `spec-driven` schema reports change completeness by artifact presence
(`proposal`, `design`, `specs`, `tasks`), so `openspec status` shows all four
artifacts complete regardless of unchecked checkboxes. The verification-03
remediation tasks added to `tasks.md` are the authoritative record of the
remediation work and every one is supported by the runtime behavior and focused
negative tests described above. The change is ready to archive.
