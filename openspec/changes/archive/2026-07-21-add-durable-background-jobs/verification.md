# Verification Evidence

This matrix maps every scenario in this change to executable evidence. Test
paths are relative to `backend/` unless otherwise stated.

| # | Capability | Scenario | Executable evidence |
|---:|---|---|---|
| 1 | durable-background-jobs | Job scheduling succeeds | `tests/test_jobs_repository.py::test_enqueue_creates_pending_job`; `tests/integration/test_durability.py::TestSessionDurability::test_job_survives_session_replacement` |
| 2 | durable-background-jobs | Scheduling transaction rolls back | `tests/integration/test_jobs_concurrency.py::TestTransactionDurability::test_rollback_removes_enqueued_job`; `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_rollback_persists_neither_response_nor_job` |
| 3 | durable-background-jobs | Concurrent workers claim work | `tests/integration/test_jobs_concurrency.py::TestConcurrentClaiming::test_two_workers_cannot_claim_same_job` |
| 4 | durable-background-jobs | Worker renews a lease | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_active_handler_renews_lease`; `tests/integration/test_jobs_concurrency.py::TestConcurrentClaiming::test_renewed_lease_can_finalize` |
| 5 | durable-background-jobs | Worker loses lease ownership | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_lease_loss_suppresses_stale_finalization`; `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_finalization_lease_loss_records_one_bounded_outcome`; `tests/integration/test_jobs_concurrency.py::TestConcurrentClaiming::test_stale_token_cannot_finalize_after_reassignment` |
| 6 | durable-background-jobs | Worker crashes during execution | `tests/integration/test_worker_lifecycle.py::TestWorkerExecution::test_crash_followed_by_expiry_allows_recovery`; `tests/integration/test_worker_scenarios.py::TestWorkerShutdown::test_drain_timeout_leaves_recoverable_state` |
| 7 | durable-background-jobs | Expired job has exhausted attempts | `tests/integration/test_jobs_concurrency.py::TestReconciliation::test_exhausted_expired_jobs_become_failed`; `tests/integration/test_worker_lifecycle.py::TestWorkerExecution::test_final_attempt_becomes_failed` |
| 8 | durable-background-jobs | Retryable handler failure | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_retryable_failure_returns_to_pending`; `tests/integration/test_worker_lifecycle.py::TestWorkerExecution::test_retry_uses_exponential_backoff_and_cap` |
| 9 | durable-background-jobs | Non-retryable handler failure | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_permanent_failure_terminates_immediately`; `tests/integration/test_worker_lifecycle.py::TestWorkerExecution::test_non_retryable_failure_terminates_immediately` |
| 10 | durable-background-jobs | Retry limit exhausted | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_retryable_failure_on_final_attempt_becomes_failed`; `tests/integration/test_durability.py::TestCompleteResultPersistence::test_failed_with_sanitized_error` |
| 11 | durable-background-jobs | Equivalent job is scheduled again | `tests/integration/test_jobs_concurrency.py::TestIdempotentEnqueue::test_concurrent_enqueue_returns_same_id`; `tests/test_jobs_repository.py::test_enqueue_idempotency_reuses_existing_job` |
| 12 | durable-background-jobs | Job repeats after domain commit | `tests/integration/test_validated_claim_handler.py::test_retry_after_relational_commit_inserts_missing_vector_without_duplicates`; `tests/integration/test_validated_claim_handler.py::test_retry_after_vector_insert_reuses_node_id_and_marks_complete`; `tests/integration/test_validated_claim_handler.py::test_multichunk_retries_converge_without_duplicate_effects` |
| 13 | durable-background-jobs | Unsupported payload version is claimed | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_unsupported_version_fails_without_task_exception` |
| 14 | durable-background-jobs | Handler completes all work | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_successful_handler_completes_job`; `tests/integration/test_durability.py::TestSessionDurability::test_claim_and_commit_across_sessions` |
| 15 | durable-background-jobs | Handler produces a useful partial result | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_partial_handler_records_partial_status`; `tests/integration/test_durability.py::TestCompleteResultPersistence::test_partial_with_limitations`; `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_invalid_partial_result_contract_fails_terminally` |
| 16 | durable-background-jobs | Handler cannot produce a useful result | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_permanent_failure_terminates_immediately`; `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_retryable_failure_on_final_attempt_becomes_failed` |
| 17 | durable-background-jobs | Owner reads job status | `tests/integration/test_jobs_status_api.py::TestJobStatusAPI::test_owner_reads_status`; `tests/integration/test_jobs_status_api.py::TestJobStatusAPI::test_owner_reads_terminal_metadata_without_payload_fields` |
| 18 | durable-background-jobs | Another user requests job status | `tests/integration/test_jobs_status_api.py::TestJobStatusAPI::test_foreign_owner_returns_404`; `tests/integration/test_jobs_status_api.py::TestJobStatusAPI::test_unknown_id_returns_404` |
| 19 | durable-background-jobs | User requests an internal job | `tests/integration/test_jobs_status_api.py::TestJobStatusAPI::test_internal_job_returns_404` |
| 20 | durable-background-jobs | No work is eligible | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_empty_poll_waits_for_configured_interval` |
| 21 | durable-background-jobs | Worker receives shutdown signal | `tests/integration/test_worker_scenarios.py::TestWorkerShutdown::test_module_entrypoint_handles_sigterm_cleanly`; `tests/integration/test_worker_scenarios.py::TestWorkerShutdown::test_external_cancellation_propagates_after_cleanup`; `tests/integration/test_worker_scenarios.py::TestWorkerShutdown::test_handler_completes_during_short_drain_without_new_claims`; `tests/integration/test_worker_scenarios.py::TestWorkerShutdown::test_drain_timeout_leaves_recoverable_state`; `tests/integration/test_worker_scenarios.py::TestShutdownDuringClaim::test_shutdown_before_commit_rolls_back`; `tests/integration/test_worker_scenarios.py::TestShutdownDuringClaim::test_shutdown_after_commit_releases_lease` |
| 22 | gcp-deployment-platform | Worker is deployed with backend release | `tests/deployment/test_render_worker.py::TestRenderedWorkerContract::test_render_emits_worker_deployment` |
| 23 | gcp-deployment-platform | Worker uses runtime dependencies | `tests/deployment/test_render_worker.py::TestRenderedWorkerContract::test_render_emits_worker_deployment`; `tests/deployment/test_render_worker.py::test_no_service_selects_worker_with_subset_selector_check` |
| 24 | gcp-deployment-platform | Migration Job remains separate | `tests/deployment/test_render_worker.py::TestRenderedWorkerContract::test_render_emits_native_complete_migration_job`; `tests/deployment/test_render_worker.py::test_deploy_workflow_migration_before_backend_rollout` |
| 25 | gcp-deployment-platform | Worker rollout succeeds | `tests/deployment/test_render_worker.py::test_worker_rollout_success_returns_zero`; `tests/deployment/test_render_worker.py::test_deploy_workflow_migration_before_backend_rollout` |
| 26 | gcp-deployment-platform | Worker rollout fails | `tests/deployment/test_render_worker.py::test_worker_rollout_failure_returns_nonzero_and_runs_diagnostics` |
| 27 | gcp-deployment-platform | Developer runs worker locally | `tests/deployment/test_render_worker.py::test_compose_runs_local_worker_with_postgresql_and_production_entrypoint`; `tests/integration/test_worker_observability.py::TestWorkerReadiness::test_local_runtime_uses_production_registry_and_postgresql_contracts` |
| 28 | knowledge-rag-acquisition | Assistant emits validated ingestion claims | `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_final_judge_supported_multilingual_claim_enqueues`; `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_response_persistence_and_enqueue_commit_together`; `tests/integration/test_validated_claim_handler.py::test_assistant_producer_to_real_worker_persists_once` The multilingual test proves multilingual and paraphrased semantic-judge output travels through real normalization, claim construction, assistant persistence, and durable enqueueing without keyword or language-specific routing. The provider result is deterministic and mocked; external model multilingual quality is not part of this deterministic integration test. |
| 29 | knowledge-rag-acquisition | Assistant emits no validated claims | `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_empty_claims_enqueue_nothing`; `tests/integration/test_multilingual.py::test_non_final_or_empty_semantic_states_build_no_claims` |
| 30 | knowledge-rag-acquisition | Assistant persistence rolls back | `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_rollback_persists_neither_response_nor_job` |
| 31 | knowledge-rag-acquisition | Handler retries after claim persistence | `tests/integration/test_validated_claim_handler.py::test_production_handler_persists_and_reuses_one_relational_and_vector_result`; `tests/integration/test_validated_claim_handler.py::test_retry_after_relational_commit_inserts_missing_vector_without_duplicates` |
| 32 | knowledge-rag-acquisition | Job contains multiple claim outcomes | `tests/integration/test_validated_claim_handler.py::test_permanent_claim_failure_returns_bounded_partial_result` |
| 33 | knowledge-rag-acquisition | Permanently invalid claim payload | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_invalid_payload_fails_before_handler_execution` |
| 34 | knowledge-rag-acquisition | Worker is unavailable after chat response | `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_worker_absence_does_not_remove_response` |
| 35 | knowledge-rag-acquisition | Ingestion exhausts retries | `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_exhausted_ingestion_does_not_remove_response` |
| 36 | provider-observability | Job is scheduled | `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_final_judge_supported_multilingual_claim_enqueues`; `tests/integration/test_assistant_ingestion.py::TestAssistantDurableIngestion::test_idempotent_enqueue_records_reused_schedule_metric` |
| 37 | provider-observability | Worker attempt completes | `tests/integration/test_worker_observability.py::TestEventInventory::test_runtime_attempt_events_are_complete_and_payload_safe` |
| 38 | provider-observability | Expired lease is recovered | `tests/integration/test_worker_observability.py::TestEventInventory::test_stale_recovery_event_emitted`; `tests/integration/test_worker_observability.py::TestEventInventory::test_direct_expired_claim_emits_recovery_event_and_metric` |
| 39 | provider-observability | Job backlog is observed | `tests/integration/test_worker_observability.py::test_metrics_registry_renders_required_families`; `tests/integration/test_worker_lifecycle.py::TestBacklogMetrics::test_backlog_counts_reflect_database`; `tests/integration/test_worker_observability.py::TestBacklogCollection::test_worker_backlog_metrics_through_collector`; `tests/integration/test_worker_observability.py::TestBacklogCollection::test_worker_status_metrics_include_every_lifecycle_state` |
| 40 | provider-observability | Job metric is emitted | `tests/integration/test_worker_observability.py::test_metrics_registry_rejects_unbounded_labels`; `tests/integration/test_worker_observability.py::TestTelemetrySafety::test_prometheus_labels_are_closed` |
| 41 | provider-observability | Operator correlates a job failure | `tests/integration/test_worker_observability.py::TestEventInventory::test_runtime_attempt_events_are_complete_and_payload_safe` |

## Supplemental Regression Evidence

| Regression | Executable evidence |
|---|---|
| Sensitive values absent from lifecycle logs | `tests/integration/test_worker_observability.py::TestComprehensiveSensitiveLog::test_complete_path_emits_logs_without_sensitive_values`; `tests/integration/test_worker_observability.py::TestEventInventory::test_runtime_attempt_events_are_complete_and_payload_safe`; `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_active_handler_renews_lease`; `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_lease_loss_suppresses_stale_finalization`; `tests/integration/test_worker_scenarios.py::TestWorkerShutdown::test_drain_timeout_leaves_recoverable_state` |
| Inaccessible jobs are indistinguishable | `tests/integration/test_jobs_status_api.py::TestJobStatusAPI::test_inaccessible_jobs_look_identical` |
| Service subset selectors are detected | `tests/deployment/test_render_worker.py::TestServiceSelector::test_exact_selector_match`; `tests/deployment/test_render_worker.py::TestServiceSelector::test_one_label_subset_match`; `tests/deployment/test_render_worker.py::TestServiceSelector::test_unrelated_selector`; `tests/deployment/test_render_worker.py::TestServiceSelector::test_empty_selector` |
| Result boundaries and corrupt durable metadata fail closed | `tests/test_jobs_contracts.py::test_read_job_result_enforces_documented_bounds`; `tests/test_jobs_contracts.py::test_status_deserialization_rejects_corrupt_persisted_metadata` |
| Invalid direct attempt limits fail before SQL | `tests/test_jobs_contracts.py::test_enqueue_rejects_nonpositive_attempt_limits_before_sql` |
| Concurrent production claim ingestion converges | `tests/integration/test_validated_claim_handler.py::test_concurrent_production_handlers_converge_on_one_claim` |
| Ingestion-key identity components are stable | `tests/integration/test_validated_claim_handler.py::test_ingestion_key_changes_for_stable_identity_components`; `tests/integration/test_validated_claim_handler.py::test_ingestion_key_canonicalizes_covered_aspects_and_policy_version` |
| Renderer validates worker shutdown timing | `tests/deployment/test_render_worker.py::TestRenderedWorkerContract::test_renderer_rejects_invalid_worker_shutdown_timings` |
| Unexpected and typed raised handler errors are sanitized | `tests/integration/test_worker_scenarios.py::TestWorkerPolling::test_raised_handler_errors_are_sanitized_and_finalized` |

## Final Gates

- Backend lint: `docker compose run --rm backend .venv/bin/ruff check .`
- Backend non-integration: `docker compose run --rm backend .venv/bin/pytest --ignore=tests/integration -q`
- PostgreSQL/pgvector integration: `docker compose run --rm -e TEST_DATABASE_URL=postgresql+asyncpg://fotosintesis:fotosintesis@postgres:5432/fotosintesis backend .venv/bin/pytest tests/integration -q`
- Frontend lint: `pnpm --dir frontend lint`
- Frontend typecheck: `pnpm --dir frontend typecheck`
- Frontend tests: `pnpm --dir frontend test`
- Frontend OpenAPI check: `pnpm --dir frontend openapi:check`
- Frontend build: `pnpm --dir frontend build`
- Compose: `docker compose config --quiet`
- OpenSpec: `openspec validate add-durable-background-jobs --strict`
- Worktree whitespace: `git diff --check`

`JOBS_PRODUCER_ENABLED` remains `false` in deployment and local defaults.

## Latest Verification Evidence

- UTC date: 2026-07-20T21:45:16Z
- Python: 3.12.13
- PostgreSQL/pgvector: `pgvector/pgvector:pg16`, image ID `sha256:131dcf7ff6a900545df8e7e092c270aa8c6db2f2c818e408cb45ec21316b74e6`
- Backend non-integration: 574 passed
- PostgreSQL/pgvector integration: 130 passed
- Backend full suite: 704 passed
- Deployment suite: 24 passed
- Frontend: 27 test files, 138 tests passed; lint, typecheck, OpenAPI check, and build passed
- Focused worker/concurrency/assistant/status/deployment evidence: 126 passed
- Ruff, Compose validation, and strict OpenSpec validation: passed. Kubernetes server-side dry-runs were skipped because the local GKE authentication token could not be refreshed non-interactively. Rendered dev and prod manifests passed deployment rendering tests.
- Source: `740ce4343cbe69757c6f79084cf0f29a9553e4bd` plus uncommitted changes.
- Worktree: dirty; tests ran against the uncommitted durable-job fixes and pre-existing unrelated changes shown by `git status --short`.

Exact commands run:

```bash
docker compose run --rm backend .venv/bin/ruff check .
docker compose run --rm backend .venv/bin/pytest --ignore=tests/integration -q
docker compose run --rm -e TEST_DATABASE_URL=postgresql+asyncpg://fotosintesis:fotosintesis@postgres:5432/fotosintesis backend .venv/bin/pytest tests/integration -q
docker compose run --rm backend .venv/bin/pytest tests/deployment -q
docker compose run --rm -e TEST_DATABASE_URL=postgresql+asyncpg://fotosintesis:fotosintesis@postgres:5432/fotosintesis backend .venv/bin/pytest -q
docker compose run --rm -e TEST_DATABASE_URL=postgresql+asyncpg://fotosintesis:fotosintesis@postgres:5432/fotosintesis backend .venv/bin/pytest tests/integration/test_worker_scenarios.py tests/integration/test_worker_observability.py tests/integration/test_jobs_concurrency.py tests/integration/test_assistant_ingestion.py tests/integration/test_jobs_status_api.py tests/integration/test_validated_claim_handler.py tests/deployment/test_render_worker.py -q
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend openapi:check
pnpm --dir frontend build
docker compose config --quiet
openspec validate add-durable-background-jobs --strict
git diff --check
```

Server-side Kubernetes dry-run command attempted after rendering both examples:

```bash
tmp="$(mktemp -d)"
sh deploy/k8s/render.sh deploy/k8s/dev/values.env.example "$tmp/dev"
sh deploy/k8s/render.sh deploy/k8s/prod/values.env.example "$tmp/prod"
kubectl apply --dry-run=server -f "$tmp/dev/50-migrations.yaml"
kubectl apply --dry-run=server -f "$tmp/dev/55-worker.yaml"
kubectl apply --dry-run=server -f "$tmp/prod/50-migrations.yaml"
kubectl apply --dry-run=server -f "$tmp/prod/55-worker.yaml"
```

The first server-side apply was skipped because `gcloud` could not refresh an
interactive GKE credential in this environment; no client-side parse was
recorded as a server-side validation.
