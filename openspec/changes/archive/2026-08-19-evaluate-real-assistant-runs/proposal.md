## Why

The evaluation runner currently builds candidate text from `reference_output` and treats reference retrieval records and tool traces as observed behavior. Metrics are therefore artificially high while runtime behavior can regress unnoticed. Evaluation must execute the current assistant graph and score what it actually produces, and CI needs deterministic, reproducible provider behavior.

## What Changes

- Execute every evaluation case through the current assistant orchestration (`AssistantGraph`) instead of fabricating candidate output from references.
- Separate expected fixtures (input, setup state, reference text, expected relevance, tool assertions) from observed execution records (response, retrieval, tools, validation, errors).
- Capture, per case, the actual response and answer language, selected taxonomy/topic/required aspects, retrieved evidence identifiers and source metadata, tool outcomes with bounded error categories, and execution/validation errors.
- Capture bounded run metadata: provider identity, recording version, latency, and usage counters.
- Replay deterministic, versioned provider recordings at the existing provider interfaces for CI evaluation; reject missing, stale, or incompatible recordings explicitly.
- Keep live-provider evaluation as a separate opt-in operational mode that is clearly non-deterministic and records cost/variability.
- Compute text, retrieval, tool, and judge metrics from observed data only.
- Apply all configured per-case and aggregate approval thresholds; a metric runtime failure must not silently fall back to a differently named metric.
- Distinguish execution failures from low-quality successful execution in results and reports.
- Reconcile seed cases that reference tools, flows, or retrieval expectations absent from the current graph.

## Capabilities

### New Capabilities

- `assistant-evaluation-execution`: Execute and capture real assistant evaluation runs, including provider recording/replay, observed-result capture, and execution/mode reporting.

### Modified Capabilities

- `evaluation-metrics`: Score observed results (not reference-derived candidates) and apply the complete set of configured text, retrieval, tool, and judge thresholds.
- `assistant-agent`: Expose bounded, redacted traces (tool outcomes and retrieval evidence) needed by the evaluation harness without leaking sensitive or unbounded content.

## Impact

- `backend/app/evaluation/` (runner, dataset, metrics, report): refactor runner, split case/result schemas, add thresholds and execution-mode reporting.
- `backend/app/providers/`: add recording/replay adapters at the existing provider interfaces; no new provider boundary.
- `backend/app/assistant/`: add bounded tool/retrieval trace capture to graph state and tools facade.
- `backend/app/evaluation/data/seed_cases.json`: rework seed cases to separate setup, references, and assertions; reconcile unsupported tools/flows.
- `backend/tests/test_evaluation_pipeline.py` and related tests: update tests that assert reference-derived perfect results.
