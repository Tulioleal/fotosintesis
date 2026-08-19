## Context

The evaluation runner in `backend/app/evaluation/runner.py` never executes the assistant. It fabricates candidate text from `case.reference_output` (`_deterministic_output`) and reads `case.retrieved_documents` and `case.tool_trace` — reference fixtures — as if they were observed behavior. Metrics therefore describe the seed data, not the system, and a regression in the assistant graph cannot change a score. `backend/tests/test_evaluation_pipeline.py` currently asserts a 50/50 pass with `failed_cases == 0`.

The assistant itself is a LangGraph pipeline (`AssistantGraph`) whose dependencies flow through `AssistantTools`, which holds a `ProviderRegistry` (`app/providers/factory.py`). Every external call (text/JSON generation, search, judge, embeddings, plant data) goes through a provider interface in `app/providers/interfaces.py`. `AssistantState` (`app/assistant/graph_shared.py`) already carries the observable outputs we need — `answer`, `sources`, `diagnostics` (intent/topic/required/covered/missing aspects, `answer_language`), `tool_failures`, `fallback_reasons`, `answerability`, and `retrieval`. Tests already run the graph against an in-memory SQLite session (`backend/tests/conftest.py`) and inject a fake llamaindex runtime (`backend/tests/test_knowledge_rag.py`), so retrieval does not require a live pgvector database.

## Goals / Non-Goals

**Goals:**

- Execute the current assistant graph for every run case and score what it actually produces.
- Make CI evaluation deterministic and reproducible via versioned provider recordings replayed at the existing provider boundaries.
- Separate expected fixtures from observed records in the dataset and result schemas.
- Apply the complete set of documented thresholds and distinguish execution errors from quality failures in results and reports.
- Provide a clearly separated opt-in live mode.

**Non-Goals:**

- No new provider boundary, no HTTP/VCR-style recording layer, and no general-purpose recording framework.
- No parallel "simulated assistant" — the existing graph is the only execution path.
- No persistence of raw user conversations, prompts, source bodies, or credentials in results or reports.
- No attempt to implement every tool or flow referenced by historical seed cases; unsupported cases are reconciled or marked, not faked.
- Live mode is not part of CI.

## Decisions

### 1. Recordings are adapters over the existing provider interfaces

Implement record/replay as thin adapters implementing `TextGenerationProvider`, `JsonGenerationProvider`, `SearchProvider`, `JudgeEvaluationProvider`, `EmbeddingProvider`, and `PlantDataProvider`. A `RecordingProviderRegistry` returns a normal `ProviderRegistry` whose members are wrapped, so `AssistantTools`, `AssistantGraph`, retrieval, routing, and persistence run unchanged.

- *Alternative rejected:* a mock graph or a second "reference replay" that bypasses the graph. This would not satisfy "mutating assistant behavior changes evaluation output."
- *Alternative rejected:* a general HTTP recording proxy. The app already has clean provider interfaces; a proxy would add a deployment boundary and a much larger surface for no benefit.

### 2. One versioned recording store, keyed deterministically

A single JSON file per recording set holds `schema_version`, per-entry provider identity, and entries keyed by a stable request fingerprint:

- model text: `hash(role, "text", prompt)`
- model JSON: `hash(role, "json", prompt, canonical schema)`
- search: `hash("search", query, sorted allowed_domains)`
- embeddings: `hash("embeddings", texts)`
- plant data: `hash(provider, scientific_name, topic)`

Record mode stores the response and latency. Replay mode resolves by key and raises `RecordingMissError` on a miss and `RecordingMismatchError` on a version or provider-identity mismatch. Both are evaluation infrastructure errors, distinct from quality failures. Ordering is irrelevant because lookups are keyed, not positional.

- *Alternative rejected:* positional replay (first call → first entry). Positional replay breaks silently when graph routing changes; keyed lookup fails loudly on a real mismatch, which is the desired CI behavior.

### 3. The runner executes the graph against an isolated session

`EvaluationRunner` builds `AssistantTools` + `AssistantGraph` with the recorded `ProviderRegistry` and an isolated in-memory session created the same way `backend/tests/conftest.py` does. Each case declares `setup` fixtures and the runner resets state between cases (isolation). Observed data is projected from the returned `AssistantState`. Retrieval runs through `KnowledgeRepository` with the recorded embedding provider (or an injected fake llamaindex runtime in tests), so no live pgvector instance is required.

- *Alternative rejected:* running through `AssistantService.chat`. That adds conversation persistence, job enqueueing, and more state to reset per case without producing any additional observable signal — the graph state already contains the answer, sources, diagnostics, and tool failures.

### 4. Observed records are a bounded projection, plus one minimal trace list

The captured result is a new `ObservedCaseResult` (or an extension of `CaseResult`) projecting only bounded, non-sensitive fields from `AssistantState`: `response`, `answer_language`, operational taxonomy, `topic`, `required/covered/missing_aspects`, retrieved document ids, source metadata, `answerability_status`, `tool_calls`, and `errors`.

The single piece of new instrumentation is a bounded `tool_calls` list appended to graph state by the `AssistantTools` facade (name, success, bounded error category). No prompt text, source bodies, raw model reasoning, or credentials are captured.

- *Alternative rejected:* a general-purpose tracing/tool-telemetry framework. The facade is already the chokepoint where every tool returns a `ToolResult`; a bounded list there is sufficient and avoids instrumenting every node.

### 5. Thresholds are data-driven, not a new framework

An `EvaluationProfile` (dataclass, defaults in `app.core.settings`) declares required thresholds: BERTScore F1, ROUGE-L, retrieval recall@5 and precision@5, `tool_success_rate`, judge passing score, and an aggregate pass rate. The runner applies every configured threshold from observed data. A metric runtime failure (e.g. BERTScore model unavailable) becomes a `metric_error` and never falls back to a differently named metric — that is already the contract in `evaluation-metrics`.

- *Alternative rejected:* a per-case ad-hoc `if score < X` spread across the runner. Centralizing thresholds keeps approval auditable and makes the report show exactly which thresholds were applied.

### 6. Three execution modes; reference mode cannot pass

`mode` is `recorded` (default, CI), `live` (opt-in, real providers, records cost/variability/failures), or `reference` (renders expected data for debugging only). `reference` is rejected as a passing mode at the runner level — a run in reference mode cannot produce a passing aggregate regardless of scores.

### 7. Reports and result JSON separate error classes

Per-case `status` is one of `passed`, `quality_failure`, `execution_error`, `metric_error`, or `unsupported`. Run-level metadata adds `mode`, `recording_version`, and the applied threshold profile. `unsupported` is used when reconciliation finds a case whose expected tools or flows are absent from the current graph.

## Risks / Trade-offs

- **Recordings become stale as the graph or providers change** → Version the store against provider identity and a schema version; a mismatch raises `RecordingMismatchError` instead of replaying silently.
- **Database state leaks between cases** → The runner resets/recreates the isolated session per case; fixture setup is per-case and idempotent.
- **Instrumentation exposes sensitive data** → Capture only identifiers and bounded error categories; no prompts, source bodies, user notes, or credentials.
- **CI runtime grows** → Keep a required recorded-mode core suite and allow tagged suites for slower flows; do not make live mode part of CI.
- **Some seed cases reference tools/flows absent from the graph** → Reconcile at load time: update supported cases, and mark unsupported ones explicitly rather than fabricating traces.
- **Replaying the real graph depends on retrieval behavior** → Retrieval uses the repository with recorded embeddings or an injected fake runtime; cases that cannot be exercised in the available environment are marked `unsupported`, not skipped silently.

## Migration Plan

1. Introduce recording adapters and the `RecordingProviderRegistry` behind a `mode` flag; existing mock/live providers are unchanged.
2. Refactor `EvaluationRunner` to execute the graph and project `AssistantState`; keep the old reference-only path as `reference` mode (non-passing) during transition.
3. Split `EvaluationCase` and add `ObservedCaseResult`/threshold profile; update `seed_cases.json` and mark unsupported cases.
4. Record a CI recording set, wire the required recorded-mode suite, and update `test_evaluation_pipeline.py` assertions that assumed perfect reference-derived scores.
5. Rollback is per-step: each step is additive until the seed data and test assertions are switched, and the `reference` mode remains available as a debugging escape hatch.

## Open Questions

- Whether the required CI recording set is committed to the repo or generated in a prior CI step and cached. (Recommended: commit a versioned recording set and regenerate only when the graph or provider contract changes.)
- Exact shape of per-case `setup` fixtures for the flows that need seeded knowledge documents or garden state.
