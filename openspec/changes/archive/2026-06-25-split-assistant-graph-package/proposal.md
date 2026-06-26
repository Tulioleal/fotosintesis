## Why

`app/assistant/graph.py` has grown into a 3,000+ line god-file that mixes graph topology, assistant node orchestration, classifier prompts, answerability validation, web evidence processing, answer generation, plant-name resolution, safety routing, fallback recovery, and test-patched private helpers. This makes changes risky, slows review, and encourages tests to patch implementation details through a single oversized module.

This change decomposes the assistant graph into a focused `app/assistant/graph/` package while preserving the existing public import surface through a thin `app/assistant/graph.py` re-export shim.

## What Changes

- Split `app/assistant/graph.py` into an `app/assistant/graph/` package with one concern per submodule.
- Move assistant graph data contracts to `app/assistant/graph/types.py`, including `AssistantState`, `FallbackResponseDraft`, and `AnswerabilityResult`.
- Move module-level graph constants to `app/assistant/graph/constants.py`.
- Move pure helpers, logging helpers, and small coercion utilities to `app/assistant/graph/helpers.py`.
- Move classifier prompts and classifier execution logic to `app/assistant/graph/classifier.py`.
- Move answerability judging, evidence validation, diagnostics, and fallback-recovery checks to `app/assistant/graph/answerability.py`.
- Move web evidence, usable web result filtering, validation metadata, and source extraction helpers to `app/assistant/graph/web_evidence.py`.
- Move answer generation, fallback drafts, generation recovery, and answer cleanup helpers to `app/assistant/graph/answers.py`.
- Move prompt builders to `app/assistant/graph/prompts.py`.
- Move safety-sensitive routing helpers to `app/assistant/graph/safety.py`.
- Move plant name resolution, display-name selection, taxonomy context, and selected-plant disambiguation helpers to `app/assistant/graph/plant_resolution.py`.
- Move routing predicates to `app/assistant/graph/routes.py`.
- Move graph compilation and sequential fallback execution to `app/assistant/graph/topology.py`.
- Move the `AssistantGraph` class to `app/assistant/graph/facade.py` and convert its node/helper methods into one-line delegates to the owning submodules.
- Keep `app/assistant/graph.py` as a compatibility shim that re-exports the existing public and test-imported symbols.
- Update tests to monkeypatch canonical module paths, for example `app.assistant.graph.answerability._judge_answerability`, instead of patching shim re-exports.
- Resolve the `aspect_validation_guidance` naming collision by keeping the existing public `aspect_validation_guidance` from `app.assistant.aspect_metadata` and exposing the graph-internal dict-producing helper as `_graph_aspect_validation_guidance`.
- Add or update topology-oriented tests so the compiled assistant graph keeps the same nodes, routing, and public behavior after the split.
- No HTTP API behavior, assistant response behavior, provider selection behavior, language handling, classification semantics, evidence validation semantics, or persistence behavior changes are intended.
- No breaking changes are introduced; old `from app.assistant.graph import X` imports remain valid.

## Capabilities

### New Capabilities

- `assistant-graph-modularization`: Defines the architectural contract for the assistant graph package split, including public import compatibility, canonical submodule ownership, delegation-only facade methods, topology preservation, and file-size boundaries.

### Modified Capabilities

No existing runtime capability requirements are modified. Existing assistant behavior remains covered by the current `assistant-agent` and related specifications.

## Impact

- Affected production code:
  - `app/assistant/graph.py`
  - new `app/assistant/graph/` package modules
  - any internal imports that currently reach into `app.assistant.graph`
- Affected tests:
  - `tests/test_assistant_agent.py`
  - `tests/test_graph_topology.py`
  - any test that monkeypatches `app.assistant.graph.<symbol>`
- Public import compatibility:
  - Preserved through the `app/assistant/graph.py` shim.
  - Canonical imports move to submodules under `app.assistant.graph.*`.
- API impact:
  - No HTTP endpoint, request schema, response schema, OpenAPI contract, database schema, or provider contract changes.
- Operational impact:
  - Lower review risk for future assistant changes.
  - Smaller modules suitable for file-size checks.
  - More precise monkeypatch targets in tests.
