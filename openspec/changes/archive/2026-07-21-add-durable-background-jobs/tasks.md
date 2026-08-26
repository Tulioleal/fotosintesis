## 1. Persistence and Contracts

- [x] 1.1 Add SQLAlchemy table definitions for `application_jobs`, closed lifecycle and job-type values, lease fields, attempt policy, payload/result JSON, optional user ownership, timestamps, and unique `(job_type, idempotency_key)` enforcement.
- [x] 1.2 Add an Alembic migration with job eligibility and status indexes plus a nullable unique validated-claim ingestion key that preserves existing knowledge rows.
- [x] 1.3 Add Pydantic schemas for versioned job payloads, bounded job results and errors, internal lease records, and metadata-only user status responses.
- [x] 1.4 Add validated settings and documented defaults for worker enablement, polling interval, batch size, concurrency, lease duration, renewal interval, attempt limit, exponential backoff base/cap, and shutdown drain timeout.

## 2. Job Repository and State Machine

- [x] 2.1 Implement transactional enqueueing that reuses an existing `(job_type, idempotency_key)` row and associates user-owned work without exposing payload data. (Fixed: replaced select-then-insert with SQLAlchemy `on_conflict_do_nothing` + `returning`, tested on PostgreSQL)
- [x] 2.2 Implement bounded atomic claims with PostgreSQL `FOR UPDATE SKIP LOCKED`, including eligible pending jobs and recoverable expired processing jobs.
- [x] 2.3 Implement lease renewal and conditional complete, partial, retry, and failed transitions that reject stale lease owners.
- [x] 2.4 Implement typed retry classification and capped exponential backoff without parsing user-facing error strings. (Fixed: reconciliation now applies backoff to recovered jobs; `_finalize_job` uses `result.error.retryable` first, falls back to `_is_retryable`)
- [x] 2.5 Implement repository reads for owner-authorized status, backlog counts, oldest eligible age, and exhausted expired-job reconciliation.

## 3. Worker Runtime

- [x] 3.1 Add a closed handler registry that maps job type and supported payload version to a Pydantic-validated handler.
- [x] 3.2 Add the async worker polling loop with bounded batch claims, configurable concurrency, isolated handler sessions, and idle waiting. (Fixed: `_claim_additional_if_capacity` loop fills remaining capacity; `_cleanup_execution` tracks via `add_done_callback`)
- [x] 3.3 Add lease renewal for active handlers and safe behavior when lease ownership is lost before finalization. (Fixed: handler tasks tracked; renewal tasks cancelled on completion; `_executions` cleaned up via callback; renewal loop checks `completed.is_set`)
- [x] 3.4 Add signal handling that stops new claims, drains active handlers for the configured timeout, and leaves unfinished jobs recoverable by lease expiry. (Fixed: `_finalize_job` runs before `completed.set`; drain timeout cancels renewal tasks; lease loss suppresses all finalization)
- [x] 3.5 Add a `python -m app.jobs.worker` entrypoint that initializes existing settings, database sessions, provider registry, logging, and metrics without starting FastAPI.

## 4. Durable Validated-Claim Ingestion

- [x] 4.1 Define the versioned `ingest_validated_claims` payload and bounded result schemas using already normalized final-judge-supported claims.
- [x] 4.2 Implement a stable claim ingestion key from normalized confirmed taxonomy, source provenance, covered aspects, supported claim, evidence quote, and ingestion policy version. (Fixed: key includes source_domain; provenance preserves trusted vs external_fallback)
- [x] 4.3 Update knowledge persistence so retries reuse committed claim identities and do not duplicate documents, chunks, or embeddings. (Fixed: `save_document` and `add_embeddings` accept `commit=False`; `ingest_document` passes `commit` and `ingestion_key` through; handler commits once after atomic insert; `ingestion_key` assigned on initial insert)
- [x] 4.4 Implement the durable claim handler with per-attempt transaction rollback, typed retryable failures, successful/skipped/failed counts, and complete or partial outcomes. (Fixed: confidence 0.0 no longer inflated by truthiness fallback in `ingestion.py`; save_document/add_embeddings no longer self-commit; handler commits per convergent claim)
- [x] 4.5 Replace `_schedule_validated_claim_ingestion` and `_ingest_validated_claims_background` with enqueueing in the request-owned assistant persistence transaction while keeping chat response latency independent from worker execution.
- [x] 4.6 Ensure empty, insufficient, contradictory, or unsupported final-judge results produce no ingestion job and do not introduce keyword, token-presence, regex, or language-specific semantic checks.

## 5. Status API and Frontend Contract

- [x] 5.1 Add an authenticated `GET /jobs/{job_id}` backend endpoint with owner checks and identical not-found behavior for unknown, foreign, and internal jobs.
- [x] 5.2 Ensure the status response excludes raw payloads, claims, prompts, notes, source bodies, evidence quotes, tokens, and internal lease secrets.
- [x] 5.3 Regenerate the backend OpenAPI document and frontend TypeScript contracts and verify the generated contract diff.

## 6. Observability and Operations

- [x] 6.1 Add structured events for scheduling, claim attempts, lease renewal/loss, retries, stale-lease recovery, completion, partial results, terminal failures, and shutdown.
- [x] 6.2 Add bounded metrics for job outcomes, attempt duration, retries, stale-lease recovery, backlog by closed job type/status, and oldest eligible age.
- [x] 6.3 Verify metrics do not use job IDs, user IDs, conversation IDs, URLs, scientific names, raw errors, or payload values as labels and logs never include sensitive job content.
- [x] 6.4 Document operational inspection, retry exhaustion, backlog diagnosis, compatible payload-version rollout, and forward-fix recovery procedures.

## 7. Deployment and Local Runtime

- [x] 7.1 Add a Kubernetes worker Deployment using the same immutable backend image, workload identity, Cloud SQL connectivity, runtime configuration, secrets, and bounded resources without a public Service.
- [x] 7.2 Update Kustomize/deployment rendering and CI rollout verification so migrations complete before API and worker rollout success is reported.
- [x] 7.3 Add worker configuration to environment templates and document running the API and worker as separate local processes.
- [x] 7.4 Verify worker rollout failure causes deployment failure and image rollback guidance covers API/worker version compatibility with persisted payloads.

## 8. Automated Verification

- [x] 8.1 Add repository tests for enqueue idempotency, transaction rollback, owner status isolation, bounded result serialization, and PostgreSQL claim SQL behavior.
- [x] 8.2 Add concurrency tests proving two workers cannot hold the same active lease and stale workers cannot finalize after ownership changes (PostgreSQL-only).
- [x] 8.3 Add worker tests for lease renewal, crash/expiry recovery, retry backoff, non-retryable failure, attempt exhaustion, partial completion, unsupported versions, and graceful shutdown.
- [x] 8.4 Add integration tests proving a committed job survives process/session replacement and a failed handler rolls back before a later attempt succeeds.
- [x] 8.5 Add assistant ingestion tests proving responses return before worker execution, empty claim sets enqueue nothing, and retries do not duplicate documents, chunks, or embeddings.
- [x] 8.6 Add multilingual regression cases proving non-English, synonymous, and paraphrased source-supported claims reach existing semantic judging and durable enqueueing without new keyword or language-specific routing.
- [x] 8.7 Add deployment manifest tests for the dedicated worker command, matching backend SHA image, no public Service, migration ordering, and rollout checks.
- [x] 8.8 Run backend lint and full pytest coverage, OpenAPI contract verification, deployment rendering checks, and focused failure/restart tests before enabling the durable producer path.
