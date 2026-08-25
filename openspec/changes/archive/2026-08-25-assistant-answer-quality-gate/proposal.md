## Why

The evaluation harness executes the real AssistantGraph against committed recordings and computes retrieval, text, tool, and LLM-judge metrics, but nothing enforces quality. The default profile sets every threshold to 0.0 except tool assertions, making `aggregate_approved` trivially true. No CI job invokes the evaluation CLI, no run artifacts are retained, and 38 of 50 seed cases are marked unsupported, leaving 12 executable cases as the entire measurable surface. Chat-answer accuracy is currently unmeasured in practice and unenforced everywhere. The product target is a minimum LLM-judge pass rate of 0.60 across supported seed cases; today that number is neither measured nor enforceable.

## What Changes

- Define an enforceable quality gate: run approval requires a minimum LLM-judge pass rate computed over supported cases only.
- Require enforced profiles to configure non-zero thresholds; a `0.0` threshold becomes invalid configuration rather than "disabled".
- Define the pass-rate denominator as supported cases; unsupported cases are excluded from numerator and denominator.
- Add a minimum supported-case ratio so the dataset cannot silently shrink below a usable floor.
- Run the evaluation CLI in recorded mode as a CI job on backend changes; gate failures fail the build.
- Retain per-run artifacts (`report.md`, `result.json`) under a versioned runs directory with bounded retention.
- Fix the documented entrypoint (`python -m app.evaluation.runner` is a no-op; use `backend/scripts/run_evaluation.py`).
- Report gate outcomes as a structured summary: passed cases, failed cases, errors, unsupported count, per-threshold failures.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `evaluation-metrics`: Enforced profiles carry non-zero thresholds and a defined gate metric set.
- `evaluation-pipeline`: Pass rate is defined over supported cases with a minimum supported-case floor, CI enforcement, and retained artifacts.
- `assistant-evaluation-execution`: Unsupported-case reconciliation feeds the gate denominator and a shrinking dataset fails the run as a coverage failure.

## Impact

- `backend/app/evaluation/metrics.py` (`DEFAULT_EVALUATION_PROFILE` / profile validation), `runner.py`, `report.py`, `reconcile.py`.
- New CI job in `.github/workflows/backend-ci.yml` invoking `backend/scripts/run_evaluation.py --mode recorded`.
- Runs directory convention under `backend/app/evaluation/data/runs/` with retention policy.
- `DOCS/local-docker-compose.md` entrypoint correction; root `pnpm eval` script (already added).
- Tests extended for gate arithmetic, denominator exclusion, floor failure, artifact writer.
