## 1. Provider recording and replay

- [x] 1.1 Add `backend/app/evaluation/recordings.py` with `RecordingMode` (record/replay), `RecordingStore`, `RecordingMissError`, and `RecordingMismatchError`
- [x] 1.2 Define the versioned recording JSON schema with `schema_version`, per-entry provider identity, latency, and deterministic request keys
- [x] 1.3 Implement replay adapters for `TextGenerationProvider`, `JsonGenerationProvider`, `SearchProvider`, `JudgeEvaluationProvider`, `EmbeddingProvider`, and `PlantDataProvider`
- [x] 1.4 Implement record adapters that forward to real providers and store responses keyed by the deterministic fingerprint
- [x] 1.5 Add `RecordingProviderRegistry` that returns a `ProviderRegistry` with providers wrapped per the selected mode
- [x] 1.6 Add settings for evaluation mode and recording path/location

## 2. Dataset and case schema split

- [x] 2.1 Split `EvaluationCase` in `backend/app/evaluation/dataset.py` so expected fields (`reference_output`, `expected_relevant_document_ids`, tool assertions) are separate from any observed fields
- [x] 2.2 Replace fabricated `retrieved_documents` and `tool_trace` fixtures with relevance identifiers and tool assertions
- [x] 2.3 Add a `setup` field for per-case fixture state and an `unsupported`/`skip_reason` marker for reconciliation
- [x] 2.4 Rework `seed_cases.json` to separate setup, references, and assertions; mark cases whose tools/flows are absent from the graph
- [x] 2.5 Add a load-time reconciliation check that validates expected tools against the graph's available tool set

## 3. Observed result capture

- [x] 3.1 Add `ObservedCaseResult` (or extend `CaseResult`) with bounded fields for response, answer language, taxonomy, topic, required/covered/missing aspects, retrieved ids, source metadata, judge status, tool outcomes, and errors
- [x] 3.2 Add a bounded `tool_calls` list to graph state and populate it in the `AssistantTools` facade with name, success, and bounded error category only
- [x] 3.3 Ensure the assistant graph state exposes bounded retrieval evidence identifiers without full text or prompts

## 4. Runner executes the assistant graph

- [x] 4.1 Refactor `EvaluationRunner` to build `AssistantTools`/`AssistantGraph` with the recording-backed `ProviderRegistry` and an isolated session
- [x] 4.2 Replace `_deterministic_output` with graph execution and project the observed result from `AssistantState`
- [x] 4.3 Add per-case fixture setup/reset to guarantee isolation between cases
- [x] 4.4 Wire `mode` (`recorded`, `live`, `reference`) and make `reference` mode non-passing by construction
- [x] 4.5 Classify per-case status as `passed`, `quality_failure`, `execution_error`, `metric_error`, or `unsupported`

## 5. Metrics and thresholds

- [x] 5.1 Compute text, retrieval, and tool metrics from observed data in `backend/app/evaluation/metrics.py`
- [x] 5.2 Add an `EvaluationProfile` with configured per-case and aggregate thresholds (BERTScore F1, ROUGE-L, retrieval recall/precision, tool success, judge score, pass rate)
- [x] 5.3 Apply every configured threshold from observed scores and fail approval when any required threshold is missed
- [x] 5.4 Ensure metric runtime failure is classified as a metric error and never silently falls back to a differently named metric

## 6. Reports and run metadata

- [x] 6.1 Add run-level `mode`, `recording_version`, and threshold-profile metadata to `EvaluationRunResult` and the persisted JSON
- [x] 6.2 Update `render_markdown_report` to separate execution errors, metric errors, and quality failures and to state mode and recording version
- [x] 6.3 Update the run entrypoint `backend/scripts/run_evaluation.py` to select the mode

## 7. Tests and verification

- [x] 7.1 Add tests for recording record/replay, keyed lookups, and explicit miss/mismatch errors
- [x] 7.2 Add tests proving observed output changes when assistant behavior changes and reference text is never returned as candidate without graph production
- [x] 7.3 Add tests for per-case isolation, execution-error vs quality-failure classification, and unsupported-case reconciliation
- [x] 7.4 Add regression tests proving non-English, synonym, or paraphrased evidence reaches semantic judging without keyword matches
- [x] 7.5 Update `backend/tests/test_evaluation_pipeline.py` assertions that assumed reference-derived perfect results
- [x] 7.6 Record a CI recording set and verify reproducible recorded-mode runs
