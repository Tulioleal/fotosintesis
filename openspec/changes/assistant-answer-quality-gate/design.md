## Context

The harness already exists: `backend/app/evaluation/{dataset,runner,metrics,report,registry,recordings,reconcile}.py`, CLI at `backend/scripts/run_evaluation.py [--mode recorded|live|reference]`, and a committed recording set (`backend/app/evaluation/data/recordings/ci-recording.json`). The runner executes the real AssistantGraph. Threshold machinery exists and is tested (`apply_per_case_thresholds`, aggregate approval). However `DEFAULT_EVALUATION_PROFILE` zeroes everything except `tool_assertion_satisfaction=1.0`, and `aggregate_pass_rate=0.0` makes aggregate approval vacuous. Reconciliation marks 38/50 seed cases unsupported; only 12 execute today (8 assistant_rag + 4 reminders_agent). No CI workflow calls the CLI. `DOCS/local-docker-compose.md` documents a nonexistent module entrypoint.

## Goals / Non-Goals

**Goals:**

- Make chat-answer accuracy an enforceable contract: LLM-judge pass rate >= 0.60 across supported seed cases.
- Prevent silent dataset shrinkage via a supported-case floor.
- Produce durable, comparable run artifacts.
- Enforce in CI using deterministic recorded mode only.

**Non-Goals:**

- No live-mode gating; live stays opt-in and non-deterministic.
- No new metrics; reuse retrieval, text, tool, and judge metrics as configured inputs.
- No expansion of the supported-case set (that follows separately as flows ship).
- No dashboard/UI for results beyond the persisted report.

## Decisions

- **Gate definition.** A run passes when (a) every case-level configured threshold passes, (b) aggregate judge pass rate over supported cases meets the profile's `aggregate_pass_rate`, and (c) the supported-case ratio meets the configured floor. Judge score counts toward the gate; retrieval/text/tool thresholds are explicit per-profile contributors.
- **Zero is not "off".** A `0.0` threshold value is rejected at profile load. Disabling a metric's contribution removes it from the profile mapping, keeping intent explicit and testable.
- **Denominator = supported cases.** Unsupported cases appear in reports with reasons but never dilute or inflate the pass rate.
- **Supported-case floor.** Named profile setting (default 0.25 of seed cases); shortfall fails the run as coverage failure.
- **CI enforcement in recorded mode only** against the committed recording set; reference mode can never pass (existing contract).
- **Artifact retention.** Each run writes `runs/<run_id>/report.md` and `result.json`; latest-N runs retained, older pruned by the runner.
- **Failure reporting enumerates failed cases** with per-threshold failures, classifying execution/metric errors separately from quality failures.
- **Doc correction:** `backend/scripts/run_evaluation.py` is the sole documented entrypoint.

## Risks / Trade-offs

- Judge non-determinism in recorded mode is low but nonzero → flaky gates escalate to recording refresh, never silent threshold loosening.
- Strict floors may block merges during provider model drift → thresholds/floors are profile-configured; loosening is a reviewed diff.
- Committed artifacts grow the repo → retention bounded to latest runs with compact JSON.

## Migration Plan

1. Profile validation, gate arithmetic, floor, artifact writer + tests.
2. Introduce `quality_gate` profile calibrated from a baseline recorded run.
3. Add CI job; correct docs.
4. Rollback: remove the CI step; profile machinery remains inert without it.

## Open Questions

- Exact non-judge thresholds (BERTScore F1, ROUGE-L, recall@5): calibrate from baseline or start minimal?
- Artifact retention: commit latest-N in-repo vs upload as CI artifacts only?
- Rollout: blocking CI gate day one vs advisory first sprint?
