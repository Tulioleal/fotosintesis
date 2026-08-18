## Context

Authentication requests currently enter through GKE Ingress and Next.js, while FastAPI performs registration, credential verification, session persistence, and recovery-token writes. Production can run multiple frontend and backend replicas against shared PostgreSQL, so process-local counters cannot enforce a reliable boundary. Next.js currently discards backend retry metadata in key paths, the backend has no trusted source assertion, and recovery initiation can create a token row for every validly shaped request, including unknown accounts.

This change depends on the patched fail-closed Auth.js boundary from `upgrade-authjs-security-boundary` and must precede release of recovery confirmation in `complete-password-recovery`.

## Goals / Non-Goals

**Goals:**

- Enforce one distributed, configurable policy before expensive or state-changing authentication work.
- Combine source-wide and normalized account-aware limits without storing identifying limiter keys.
- Preserve indistinguishable recovery behavior and bounded retry contracts.
- Establish an explicit GKE Ingress to Next.js to FastAPI source-identity trust boundary.
- Make storage failures, retention, metrics, rollout, and rollback operationally explicit.

**Non-Goals:**

- CAPTCHA, general-purpose quotas, or replacement of password hashing, one-time recovery tokens, and session revocation.
- Claiming application limits prevent volumetric DDoS; Cloud Armor remains a complementary option.
- Implementing the complete password-recovery flow or changing existing recovery-token semantics beyond bounding writes.

## Decisions

### Use PostgreSQL-backed fixed windows with atomic upsert

Add a small limiter repository backed by the existing shared PostgreSQL deployment. Each row represents an opaque key, endpoint category, and fixed window, and an atomic `INSERT ... ON CONFLICT ... DO UPDATE ... WHERE count < limit RETURNING` operation determines admission without read-then-write races. Fixed windows provide a bounded, readily testable first policy without introducing another production service.

The policy defines independent limit rules by endpoint category and dimension. Configuration supplies positive limits, window lengths, maximum `Retry-After`, retention, and failure mode; startup validation rejects incomplete or unsafe production profiles. Expiry-indexed, batched cleanup removes stale windows.

Alternatives considered:

- In-memory counters were rejected because limits would multiply with replicas and reset on restart.
- Redis or Valkey would offer lower-latency primitives but adds infrastructure not otherwise required by the project; the limiter interface keeps that future replacement possible.
- Token buckets provide smoother limits but require more state and precision than the initial authentication boundary needs.

### Generate opaque keys with a keyed digest

Normalize account input using the same canonical email normalization as authentication, then compute a versioned HMAC digest with a dedicated runtime secret. Derive source keys from the trusted client address and HMAC them before persistence. Combine endpoint category and dimension in structured repository fields rather than logs. Key rotation is handled through a configured key version and natural expiry; no raw identifiers are persisted in limiter state or metrics.

A plain hash was rejected because low-entropy email addresses and IP addresses are enumerable offline.

### Establish the source identity at the frontend trust boundary

GKE Ingress remains the only public entry and routes authentication traffic to Next.js. Next.js accepts the client address only from the documented ingress-populated forwarding position, rejecting or conservatively collapsing identity when the trust chain is not established. Before calling FastAPI, Next.js replaces client-supplied internal limiter headers with an opaque source key plus an authenticated assertion produced with a dedicated shared secret. FastAPI validates that assertion and never treats arbitrary forwarding headers as source identity.

Registration and recovery use frontend-owned route handlers so browser requests follow the same boundary. The credentials provider and relevant Auth.js POST wrapper use the same source extraction and retry contract. Direct public FastAPI authentication access is not part of the deployment contract.

Forwarding raw addresses internally was rejected because it increases sensitive-data propagation and makes accidental logging more likely.

### Evaluate all applicable rules before authentication work

Each operation maps to a closed endpoint category. The limiter evaluates source rules and, where an account is present, normalized account rules before Argon2 work, recovery-token writes, or delivery. A request is admitted only when all required rules admit it. Repository operations use deterministic key ordering and one transaction to avoid partial consumption or deadlocks when multiple dimensions apply.

Successful credential verification may remove or relax only the account-specific credential-failure state. It does not clear source-wide state or unrelated operation limits. Rejected attempts and malformed-but-routable authentication submissions still consume the appropriate source boundary so validation cannot become an unbounded CPU path.

### Preserve neutral recovery responses while bounding side effects

Recovery initiation applies the same source and normalized account policy before account lookup-dependent side effects. Known and unknown accounts retain the same body, status behavior, and bounded retry metadata for equivalent limit state. A rejected or storage-failed request performs no token write or delivery. Recovery confirmation follows the same neutral rule once implemented by its dependent change.

**Recovery-confirmation validation scope.** Schema-invalid recovery-confirmation payloads are rejected by deterministic FastAPI validation with a generic `422` and no token-state detail; they are not subject to application limiter admission, which runs after body parsing. Token-shaped requests that reach token-state handling stay neutral regarding token existence, expiration, or use, and application source/account limits protect schema-valid guesses. Volumetric malformed traffic remains an ingress/edge concern (Cloud Armor is the optional edge control) and is explicitly not an application-limiter claim. This contract is recorded in the `authentication-abuse-controls` spec, the endpoint comments, the tests, and the verification reports so no artifact overstates malformed-token neutrality.

### Use explicit endpoint failure policies

The default production policy fails closed for credential verification, recovery initiation, and recovery confirmation when shared limiter admission cannot be established. Registration and relevant Auth.js POST categories also fail closed unless a reviewed, strictly bounded per-process emergency profile is explicitly configured. Failure responses use a generic temporarily-unavailable or neutral recovery contract and never reveal storage details or account state.

A general fail-open mode was rejected because it removes the security boundary exactly when shared storage is unavailable.

### Propagate a bounded retry contract through Next.js

Backend and frontend-owned route handlers preserve `429` and a whole-second `Retry-After`, clamped to a configured maximum. Typed frontend errors retain status and retry metadata. Forms show a generic retry message and prevent resubmission until the local deadline, while the server remains authoritative. Recovery copy stays neutral.

Auth.js currently collapses all non-success credential responses. The credentials flow will retain rate-limit classification in a bounded application-owned error path while continuing to map invalid credentials to the existing neutral error and excluding backend details from the browser session.

### Emit only closed-cardinality metrics

Extend the existing metrics registry with a counter labeled by a closed endpoint category and outcome (`allowed`, `rejected`, or `storage_failure`). Do not label or log digest keys, accounts, addresses, tokens, passwords, counts, or forwarding headers. Existing per-pod scraping provides aggregate observability across replicas.

## Risks / Trade-offs

- [Shared NATs can cause source-limit false positives] -> Use conservative source thresholds alongside narrower account thresholds, monitor only aggregate categories, and tune through validated configuration.
- [Address rotation weakens source limits] -> Apply account-aware rules and optionally add separately managed Cloud Armor volumetric controls.
- [Fixed-window boundaries permit short bursts] -> Choose conservative documented thresholds and migrate behind the limiter interface if production evidence requires a token bucket.
- [Database contention affects authentication latency] -> Keep rows narrow, use one atomic statement per evaluated policy, index expiry, batch cleanup, and load-test hot keys.
- [Multiple required rules can be partially consumed] -> Evaluate them in one transaction with stable lock ordering and roll back all consumption when any rule rejects.
- [Proxy misconfiguration merges users or trusts spoofed input] -> Validate deployment settings, use a conservative unknown-source bucket, authenticate internal assertions, and add rendered-manifest and end-to-end spoofing tests.
- [Retry UI can drift from server time] -> Treat the countdown as guidance only and keep every server request subject to authoritative enforcement.
- [HMAC rotation temporarily splits limits] -> Version keys, rotate only with a documented overlap or accepted conservative reset, and keep retention shorter than secret retirement.

## Migration Plan

1. Add the limiter table, expiry index, repository, policy configuration, HMAC secrets, metrics, and cleanup command; deploy the migration before application code.
2. Add source extraction and authenticated source assertion to Next.js and FastAPI, initially observing identity categories without logging identifiers.
3. Route registration and recovery through the frontend boundary and add limiter enforcement in dev environments with conservative high thresholds, validating aggregate outcomes and latency (there is no disabled report-only mode; disabled mode emits no limiter outcomes).
4. Enable enforcement by endpoint category, beginning with recovery writes and credential verification, then registration and relevant Auth.js POST operations.
5. Deploy frontend retry handling and run concurrency, spoofing, storage-failure, known-versus-unknown recovery, and multi-replica acceptance tests.
6. Roll back application enforcement by redeploying the prior application images; retain the additive table and secret safely until the old version is stable, then remove stale limiter rows through normal cleanup. Do not use fail-open configuration as rollback.

## Open Questions

- Final per-environment thresholds, windows, and maximum retry duration require security and operations review before implementation is enabled.
- Confirm the exact forwarding-header position guaranteed by the selected GKE Ingress mode and document it in deployment configuration and tests.
- Decide whether cleanup runs as a Kubernetes CronJob or as a bounded opportunistic maintenance operation after measuring expected limiter-row volume.
