## 1. Policy and Configuration

- [x] 1.1 Confirm `upgrade-authjs-security-boundary` is applied and document reviewed per-environment limits, windows, maximum retry duration, retention, and endpoint failure policies.
- [x] 1.2 Add validated backend and frontend settings for closed endpoint categories, limit profiles, trusted proxy handling, HMAC key versions, internal source assertions, cleanup, and safe production defaults.
- [x] 1.3 Add shared policy types and a limiter interface that represent source and account dimensions, admission outcomes, retry timing, and storage failures without accepting raw identifiers as metric labels.

## 2. Persistent Limiter State

- [x] 2.1 Add the limiter-state table, uniqueness constraints, expiry index, and Alembic migration following the current migration head.
- [x] 2.2 Implement keyed HMAC derivation for normalized account and trusted source identifiers with versioned keys and no raw identifier persistence.
- [x] 2.3 Implement PostgreSQL atomic multi-rule admission in stable key order and one transaction so concurrent requests cannot exceed bounds or partially consume rejected policies.
- [x] 2.4 Implement account-specific credential-state relaxation after successful login without clearing source-wide or unrelated limits.
- [x] 2.5 Implement indexed, idempotent, bounded cleanup for expired limiter windows.

## 3. Trusted Source Boundary

- [x] 3.1 Implement and unit-test GKE ingress-aware client-address extraction in the Next.js server boundary, including conservative missing-chain behavior and rejection of spoofed forwarding entries.
- [x] 3.2 Implement opaque source-key forwarding from Next.js with a signed internal assertion while stripping any client-supplied internal limiter headers.
- [x] 3.3 Validate the internal source assertion in FastAPI and apply the conservative missing-source policy instead of trusting forwarding headers or unauthenticated source keys.
- [x] 3.4 Route registration and recovery initiation through frontend-owned handlers so all browser authentication requests use the same trusted source boundary and preserve backend status, body, and `Retry-After`.

## 4. Backend Enforcement

- [x] 4.1 Add a limiter service that evaluates every applicable source and account rule before password hashing, credential verification, recovery-token persistence, or recovery delivery work.
- [x] 4.2 Enforce registration and credential-verification limits with bounded `429` responses and the documented successful-login relaxation behavior.
- [x] 4.3 Enforce recovery-initiation limits while preserving equivalent known-and-unknown body, status, retry metadata, and side-effect behavior.
- [x] 4.4 Apply the recovery-confirmation policy at its existing prepared endpoint and expose the reusable enforcement boundary required by `complete-password-recovery`.
- [x] 4.5 Implement and test each endpoint's fail-closed or explicitly bounded storage-failure response without exposing account or storage details.
- [x] 4.6 Update FastAPI response schemas and OpenAPI output for the bounded rate-limit contract, then regenerate and verify the typed frontend client.

## 5. Auth.js and Frontend Behavior

- [x] 5.1 Wrap relevant unauthenticated Auth.js POST operations with source-aware enforcement while preserving session reads, callback routing, server-only credentials, and logout semantics.
- [x] 5.2 Preserve credential-verification rate-limit classification and bounded retry metadata through Auth.js without changing neutral invalid-credential behavior or exposing backend details.
- [x] 5.3 Extend typed frontend API errors to retain `429` status and clamped `Retry-After` metadata through registration and recovery route handlers.
- [x] 5.4 Update login, registration, and recovery forms to show generic retry timing and prevent resubmission until allowed while keeping recovery copy neutral and accessible.

## 6. Observability and Operations

- [x] 6.1 Add limiter counters with closed endpoint-category and outcome labels for allowed, rejected, and storage-failure decisions, and verify no sensitive values enter metrics or logs.
- [x] 6.2 Add the cleanup execution path and deployment scheduling selected from the design open question, with bounded batches and operational failure visibility.
- [x] 6.3 Update Kubernetes manifests, renderer values, External Secrets mappings, and deployment tests for compatible policy settings, HMAC secrets, internal assertion secrets, and trusted proxy configuration across replicas.
- [x] 6.4 Document the exact GKE ingress trust chain, policy tuning, secret rotation, cleanup, metrics, incident behavior, rollout, and rollback without using fail-open as rollback.
- [x] 6.5 If required by operations, add and document Cloud Armor volumetric protection as a separate optional control that does not replace application limits.

## 7. Verification

- [x] 7.1 Add backend endpoint tests for every limit, pre-work rejection, successful-login relaxation, bounded retry values, storage failure, and recovery equivalence for known and unknown accounts.
- [x] 7.2 Add PostgreSQL integration tests proving atomic bounds under concurrent requests, consistent enforcement through separate repository instances, and cleanup safety during active updates.
- [x] 7.3 Add frontend route, Auth.js, and component tests for source propagation, spoof rejection, `429` and `Retry-After` propagation, retry presentation, disabled resubmission, and neutral recovery behavior.
- [x] 7.4 Add deployment-level verification that combined invalid credential attempts through at least two application instances cannot exceed the shared limit.
- [x] 7.5 Add privacy regression tests proving limiter state contains only opaque keyed digest keys (never passwords, tokens, emails, raw account IDs, or raw source addresses) and that responses, application logs, and metrics contain no password, token, email, raw account ID, raw source address, or digest key; metric labels are exactly the closed `category` and `outcome` pair.
- [x] 7.6 Run backend lint and test suites, migration upgrade/downgrade tests, frontend lint/typecheck/component tests, generated-contract verification, production build, and authentication Playwright journeys.

## 8. Verification-03 Remediation

- [x] 8.1 Enforce safe production configuration invariants at startup: `APP_ENV` in `prod`/`production` requires `AUTH_LIMITER_ENABLED=true`; account profiles for `credential_verification`, `recovery_initiation`, and `recovery_confirmation` are required when enforcement is enabled; `AUTH_LIMITER_MAX_RETRY_AFTER_SECONDS` and `LimiterPolicy.max_retry_after_seconds` reject zero; registration and `authjs_post` may stay source-only.
- [x] 8.2 Deploy the cleanup CronJob: validate `56-limiter-cleanup.yaml` in the server-side dry-run loop, apply it idempotently after migrations and before rollout, keep the Cloud SQL proxy native-sidecar structure, and prove the workflow path and rendered dev/prod CronJobs in deployment tests.
- [x] 8.3 Replace the multi-instance acceptance test with genuinely independent application boundaries: two `create_app()` objects, instance-local session overrides and engines, one shared PostgreSQL schema, and proof that both application-local stacks handled requests and the combined admitted 401s equal the shared account bound.
- [x] 8.4 Apply one authoritative bounded retry policy to both normal rejection and storage failure: `raise_storage_failure()` uses the admission outcome's clamped retry within the validated positive policy maximum, keeps 503 and 429 distinct, preserves neutral recovery bodies, and never emits a zero `Retry-After`.
- [x] 8.5 Separate Auth.js unavailable and limited states: a distinct bounded unavailable code and `CredentialsUnavailable` error for backend 503 and unexpected admission failures, generic temporary-unavailability feedback without "too many attempts", and strict code parsers that reject malformed or oversized codes.
- [x] 8.6 Correct verification evidence: strengthen trusted-proxy route-level spoofing coverage (documented as contract-level integration evidence, not a live deployment test), add an Auth.js stub mode that rate-limits only credential verification, and keep task 7.6 incomplete until the full matrix is reproducible.
- [x] 8.7 Align recovery-confirmation validation claims and documentation with practical scope: schema-invalid requests may return deterministic 422 validation errors, token-shaped guesses stay neutral, and design, comments, tests, and verification reports state the same contract.
- [x] 8.8 Complete privacy evidence across every output surface and correct operational documentation: actual digest keys absent from responses, logs, and metric labels; metric label set exactly `{category, outcome}`; recovery-token and password sentinels; remove the nonexistent report-only rollout; correct HMAC rotation and cleanup deployment claims.
- [x] 8.9 Run the complete reproducible verification matrix (Python 3.12 Docker Compose backend unit and PostgreSQL integration suites, deployment-render tests, sequential frontend gates, OpenSpec strict validation, `git diff --check`) and record exact versions, commands, counts, and skipped live-cloud checks.
