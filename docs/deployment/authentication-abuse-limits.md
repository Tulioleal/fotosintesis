# Authentication Abuse Limits: Deployment and Operations

This document is the operational companion to the
[Authentication Abuse Limits policy](../authentication-abuse-limits.md).
It describes the exact GKE ingress trust chain, secret provisioning, policy
tuning, cleanup, metrics, incident behavior, rollout, and rollback for the
distributed authentication limiter.

## GKE Ingress Trust Chain

Authentication traffic flows only through `GKE Ingress -> Next.js -> FastAPI`.

- GKE Ingress (an external Application Load Balancer) is the only public entry
  point. The load balancer appends **two** addresses to the `X-Forwarded-For`
  chain, in this order: `<client-ip>,<load-balancer-ip>`. The final entry is
  the load balancer's own forwarding-rule address and is **never** the client.
  Everything before `<client-ip>,<load-balancer-ip>` is client-supplied,
  unverified by the platform, and never used as limiter identity.
- The frontend deployment sets `AUTH_LIMITER_TRUSTED_FORWARDED_HOPS=2`. The
  frontend reads only the first of the two trailing platform-appended entries
  as limiter source identity and ignores every earlier client-supplied entry.
  A missing, short, or non-IP platform chain fails conservatively (no trusted
  source identity).
- Before calling FastAPI, the frontend builds internal requests from an
  **allowlist**: only `Content-Type: application/json` plus the generated
  opaque source key and HMAC assertion (`AUTH_LIMITER_ASSERTION_SECRET`). Raw
  forwarding headers (`X-Forwarded-For`, `Forwarded`), cookies, and any
  client-supplied `x-fotosintesis-source-key` / `x-fotosintesis-source-assertion`
  values never reach FastAPI.
- FastAPI validates the assertion with the same shared secret. A request
  without a valid assertion applies the conservative missing-source policy
  (rejected without consuming any source rule). Direct public FastAPI
  authentication access is not part of the deployment contract.

If the actual GKE ingress forwarding behavior ever changes, update the trusted
hop count in `deploy/k8s/render.sh`, the values files, and the
`source-identity.test.ts` suite together — never at runtime only. Reference:
Google Cloud "External Application Load Balancer overview" (`X-Forwarded-For`
header section).

### Evidence scope for spoofing coverage

Spoofing coverage is **contract-level integration evidence**, not a live
deployment test: the unit and route-level suites inject attacker-prepended,
trusted-client, and load-balancer entries exactly as the Google forwarding
contract describes and prove the generated source key corresponds only to the
trusted client, that raw forwarding headers and cookies never cross the
frontend boundary, and that a malformed platform suffix produces no trusted
assertion (the backend then applies the conservative missing-source policy).

Evidence types are intentionally distinguished:

- **Unit tests** prove the source-extraction and key-derivation primitives.
- **Integration tests** (two independent application objects against shared
  PostgreSQL) prove the distributed bound and the frontend/backend assertion
  handshake.
- **Stub E2E tests** prove the Auth.js wrapper, credential path, and form
  behavior against a deterministic backend stub.
- **Live-cloud validation** (an actual GKE ingress spoofing test, Cloud Armor
  policy behavior, and production traffic) is **optional operational
  follow-up**, not completed evidence, and is explicitly out of scope for this
  project.

## Secret Provisioning

Two shared secrets back the limiter. They MUST be identical across every
frontend and backend replica and MUST be provisioned in Secret Manager before
enabling `AUTH_LIMITER_ENABLED=true`:

| Secret Manager container | Projected key | Used by |
| --- | --- | --- |
| `fotosintesis-auth-limiter-hmac-secret` | `auth-limiter-hmac-secret` | Frontend source-key derivation and backend keyed digests |
| `fotosintesis-auth-limiter-assertion-secret` | `auth-limiter-assertion-secret` | Frontend assertion signing and backend assertion validation |

Add the containers to `var.secret_ids` in
`infra/opentofu/envs/{dev,prod}` and populate values out of band (they are
never committed). The `80-external-secrets.yaml` manifest already projects
them into the runtime Secret.

### HMAC key rotation

- The configured key version is included in the HMAC **input** (`version`,
  dimension, identifier), not prefixed to stored values.
- Only one active key/version is currently supported; there is no overlap mode.
- Rotating the HMAC secret therefore resets or partitions the active counters:
  either accept the conservative counter reset (documented with operations) or
  partition counters per version. Retention (`AUTH_LIMITER_RETENTION_SECONDS`)
  must stay shorter than secret retirement so stale digests never outlive keys.
- Never use fail-open configuration as a rotation or rollback mechanism.

## Policy Tuning

Limits, windows, retry caps, retention, and storage-failure modes are
configured through validated settings only (never code edits):

- `AUTH_LIMITER_PROFILES` is a JSON object covering every closed endpoint
  category. Startup validation rejects missing categories, unknown
  categories, and non-positive limits.
- `AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS` clamps every `Retry-After`.
- `AUTH_LIMITER_RETENTION_SECONDS` bounds limiter state lifecycle.
- `AUTH_LIMITER_CLEANUP_BATCH_SIZE` bounds each cleanup batch.

Production values are reviewed with security and operations and recorded in
the [policy document](../authentication-abuse-limits.md). Monitor only
aggregate categories (see Metrics) and tune conservatively to tolerate
shared-NAT aggregation.

## Cleanup

Expired limiter windows are removed by the `fotosintesis-limiter-cleanup`
Kubernetes CronJob (`deploy/k8s/base/56-limiter-cleanup.yaml`), which runs
`scripts.cleanup_limiter_state` every 30 minutes. The deployment workflow
validates the manifest with a server-side dry run and applies it idempotently
after migrations complete and before any application code is deployed; a
deployment never triggers a one-off cleanup Job. The operation:

- runs in bounded batches (`AUTH_LIMITER_CLEANUP_BATCH_SIZE`, default 1000);
- is idempotent and safe under concurrent admissions;
- removes only rows whose `window_end` has passed the retention cutoff
  (`AUTH_LIMITER_RETENTION_SECONDS`), preserving rows inside retention;
- has `concurrencyPolicy: Forbid` so overlapping runs never race;
- surfaces failures as failed CronJob Pods for alerting.

## Metrics

The backend exposes `fotosintesis_limiter_outcomes_total` on the existing
`/metrics` endpoint with ONLY closed labels:

- `category` in `{registration, credential_verification, recovery_initiation,
  recovery_confirmation, authjs_post}`
- `outcome` in `{allowed, rejected, storage_failure}`

No account, source address, digest key, count, password, or token ever enters
metric labels or logs. Existing `PodMonitoring` discovers the metric across
replicas; aggregate with `sum` for decisions because each replica counts its
own decisions.

## Incident Behavior

- **Shared storage unavailable**: every covered endpoint fails closed. Responses
  are generic `503` for non-recovery endpoints and the neutral recovery contract
  for recovery endpoints; they never reveal account or storage details. Verify
  via the `storage_failure` outcome metric.
- **Spoofed forwarding headers**: the frontend ignores untrusted entries and
  the backend rejects unauthenticated source keys; no attacker-selected limiter
  identity is created. Verify with the deployment spoofing tests.
- **Source false positives behind a shared NAT**: account-aware rules still
  bound credential and recovery attempts; tune source thresholds through
  validated configuration and optionally add Cloud Armor volumetric controls.

## Rollout

1. Deploy the `0015_auth_limiter_state` migration before application code so
   the table exists before enforcement. The deploy workflow applies the
   cleanup CronJob after migrations and before application code.
2. In a dev environment, deploy enforcement **enabled** with conservative high
   thresholds and monitor the aggregate `fotosintesis_limiter_outcomes_total`
   outcomes and latency before raising thresholds in production. There is no
   disabled "report-only" mode: disabled mode emits no limiter outcomes, so it
   cannot validate enforcement behavior.
3. Production **refuses to start** with `AUTH_LIMITER_ENABLED` not `true`; the
   deploy workflow also verifies the limiter secrets are projected before
   rollout.
4. Tune thresholds by endpoint category through validated configuration
   (never code edits) and run concurrency, spoofing (contract-level), storage
   failure, known-versus-unknown recovery, and multi-replica acceptance tests
   (see the change verification tasks).

## Rollback

Roll back application enforcement by redeploying the prior application images;
do **not** use fail-open configuration as rollback. The additive table and
secrets remain safe until the old version is stable; stale limiter rows are
removed by normal cleanup. Once the old version is stable, retain the secrets
and table per the retention contract.

## Cloud Armor Volumetric Protection (Optional, Complementary)

The distributed application limits bound account-sensitive authentication
work (password hashing, token writes, delivery) and are always enforced
regardless of any edge policy. Volumetric protection at the edge is a
**separate, optional** control and MUST NOT replace application limits.

If operations decide to add it:

- Configure a Cloud Armor security policy with volumetric rate limits
  (e.g., per-IP request rate / burst) and attach it to the global external
  HTTPS load balancer backing the GKE Ingress.
- Keep the application `AUTH_LIMITER_PROFILES` thresholds conservative so a
  Cloud Armor policy change — or its absence — never weakens the distributed
  source-aware and account-aware boundary.
- Tune Cloud Armor thresholds independently of the application profiles;
  changing or removing the edge policy leaves application limits enforced.
- Document the policy name, thresholds, and review owner alongside this file.
