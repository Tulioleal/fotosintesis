## Context

The backend evaluation pipeline already computes judge results, records failure reasons, calculates `failed_action_claim_rate`, and marks cases as failed when judge or tool-action failure conditions are present. Current tests cover the happy path for the seed dataset and basic text/retrieval metrics, but they do not directly exercise these negative paths.

## Goals / Non-Goals

**Goals:**
- Add targeted backend regression tests for judge failure handling.
- Add targeted backend regression tests for failed tool actions that are claimed as successful.
- Verify both in-memory run results and persisted result JSON capture the expected failed state and reasons.

**Non-Goals:**
- Change evaluation runner, metric, report, or dataset behavior.
- Add new external judge providers or seed cases.
- Broaden the evaluation rubric or add new metrics.

## Decisions

- Keep coverage in `backend/tests/test_evaluation_pipeline.py` because the existing file already owns evaluation runner and metric tests. Alternative considered: creating a new test module. A new module is unnecessary for two focused regression tests.
- Build minimal `EvaluationCase` instances in the tests instead of modifying seed data. This avoids changing the canonical 50-case dataset and keeps failure scenarios isolated from the happy-path aggregate test.
- Exercise `EvaluationRunner.run(..., cases=[...])` for failure scenarios instead of private methods. This verifies summary generation and persisted output along with per-case failure state.
- Use the deterministic local judge for the tool-failure scenario and a small fake `JudgeEvaluationProvider` for the explicit judge-failure scenario. This covers both implemented failure paths without network or provider dependencies.

## Risks / Trade-offs

- Test assertions may become brittle if failure reason text changes -> Assert stable substrings or exact reasons only where they are part of the expected contract.
- Persisted JSON checks add file I/O to tests -> Use `tmp_path` to keep tests isolated and fast.
- Custom cases must satisfy the `EvaluationCase` schema -> Construct them with the existing Pydantic models rather than raw dictionaries where possible.
