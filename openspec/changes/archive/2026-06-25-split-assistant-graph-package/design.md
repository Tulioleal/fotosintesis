## Context

`app/assistant/graph.py` currently owns the assistant graph's runtime topology and most of the assistant's supporting behavior. The file contains the `AssistantGraph` class, state types, answerability models, classifier prompts, evidence validators, fallback drafts, web evidence helpers, route predicates, prompt builders, plant-name helpers, safety helpers, graph compilation, and the sequential fallback graph. It is over 3,000 lines long and is the central place where unrelated changes collide.

Tests also depend on this concentration of logic. `tests/test_assistant_agent.py` imports and monkeypatches many private helpers through `app.assistant.graph.<symbol>`, because those helpers currently have no canonical home. A simple physical split is not enough: tests that patch shim re-exports would not affect the actual submodule implementation if the implementation uses its own local symbols. Therefore, test monkeypatch targets must move to canonical submodule paths as part of this change.

The refactor is strictly architectural. It must preserve assistant runtime behavior, graph topology, public imports, multilingual classification behavior, answerability semantics, evidence validation semantics, fallback routing, provider behavior, persistence behavior, and HTTP API behavior.

## Goals / Non-Goals

**Goals:**

- Replace the 3,000+ line `app/assistant/graph.py` implementation with a focused `app/assistant/graph/` package.
- Keep `app/assistant/graph.py` as a thin re-export shim so existing imports remain valid.
- Move each symbol to a canonical submodule based on ownership, not arbitrary line ranges.
- Convert `AssistantGraph` into a thin facade whose public node/helper methods delegate to submodule functions.
- Keep every graph submodule under 500 lines.
- Update tests to patch canonical submodule paths rather than compatibility-shim paths.
- Preserve all public symbols currently imported from `app.assistant.graph`, including `AssistantGraph`, `AssistantState`, `FallbackResponseDraft`, `AnswerabilityResult`, and test-imported private helpers.
- Preserve the compiled graph topology and sequential fallback behavior.
- Resolve the `aspect_validation_guidance` collision without changing existing public behavior.

**Non-Goals:**

- No change to assistant classification semantics, evidence semantics, answerability semantics, safety semantics, multilingual behavior, prompt intent, or provider selection.
- No new deterministic keyword lists, translated word lists, language-specific heuristics, or regex-based botanical semantics.
- No HTTP API change.
- No database schema change.
- No provider interface change.
- No wholesale split of `tests/test_assistant_agent.py`; tests are updated only where needed for canonical monkeypatch targets.
- No removal of compatibility shim exports in this change.

## Decisions

### Decision 1: Keep `app/assistant/graph.py` as a compatibility shim

The old module path remains valid and re-exports symbols from the new package. This minimizes downstream import churn and avoids turning an architectural split into a broad consumer migration.

Alternative considered: hard-cut all imports to the new package paths. This was rejected because it creates a larger diff and increases the chance of missing external consumers. The canonical implementation paths still move to submodules; only compatibility import paths remain.

**Implementation note:** Because the new layout is a `graph/` package directory, the compatibility shim lives in `app/assistant/graph/__init__.py` rather than a sibling `graph.py` file. Python cannot have both a `graph.py` file and a `graph/` package directory sharing the same parent, so the package init plays the role of the shim. `from app.assistant.graph import X` resolves to the package init either way, so this is functionally equivalent and idiomatic; spec scenarios that referred to `app/assistant/graph.py` are updated to refer to the package init.

### Decision 2: Use a package named `app/assistant/graph/` with one concern per module

The package layout is:

```text
app/assistant/graph/
├── __init__.py
├── types.py
├── constants.py
├── helpers.py
├── classifier.py
├── answerability.py
├── web_evidence.py
├── answers.py
├── prompts.py
├── safety.py
├── plant_resolution.py
├── routes.py
├── topology.py
└── facade.py
```

This layout is intentionally flatter than a deeply nested package tree. The assistant graph is already a specialized subdomain; a single package with topic modules provides enough separation while keeping imports readable.

Alternative considered: create separate `app/assistant/classifier/`, `app/assistant/answerability/`, `app/assistant/answers/`, and similar top-level packages. This was rejected for this change because it expands the scope beyond the graph extraction and makes future assistant-wide refactors harder to distinguish from graph-specific refactors.

### Decision 3: Move type contracts to `types.py`

`AssistantState`, `FallbackResponseDraft`, and `AnswerabilityResult` become the package's core data contracts and live in `app.assistant.graph.types`.

This prevents cyclic imports between the facade, routes, answerability helpers, prompt builders, and topology helpers. Submodules can import shared contracts from `types.py` without importing the facade.

### Decision 4: `AssistantGraph` becomes a facade in `facade.py`

`AssistantGraph` remains the public object constructed by `AssistantService`, but method bodies move out of the class. Each method becomes a delegate to the module that owns the concern. For example:

```python
async def classify_intent(self, state: AssistantState) -> dict:
    return await classifier.classify_intent(self, state)
```

The delegated function may receive `self` when it needs `self.tools`, `self.settings`, or other graph instance state. This preserves behavior while removing business logic from the class body.

Alternative considered: convert all delegated functions into stateless functions that take `tools` and `settings` explicitly. This is cleaner long-term but would create a larger behavior-preserving refactor in one step. Passing `self` is the minimal safe move for this change.

### Decision 5: Move monkeypatch targets to canonical submodule paths

Tests must patch the module where the implementation reads the symbol. A shim export is only an alias; patching the alias does not patch the implementation's local reference after the split.

Examples:

- `monkeypatch.setattr("app.assistant.graph._judge_answerability", ...)` becomes `monkeypatch.setattr("app.assistant.graph.answerability._judge_answerability", ...)`.
- `monkeypatch.setattr("app.assistant.graph._targeted_web_query", ...)` becomes `monkeypatch.setattr("app.assistant.graph.web_evidence._targeted_web_query", ...)`.
- `monkeypatch.setattr("app.assistant.graph._grounded_answer_prompt", ...)` becomes `monkeypatch.setattr("app.assistant.graph.prompts._grounded_answer_prompt", ...)`.

The shim remains for external consumers, but tests validate and patch the canonical implementation paths.

### Decision 6: Preserve graph topology through `topology.py`

`_compile_graph` and `_SequentialGraph` move together to `topology.py` because they jointly define graph execution. The compiled topology must remain behaviorally identical.

The topology test should assert node names and route behavior that the implementation can expose without depending on LangGraph internals more than necessary. If the project already has `tests/test_graph_topology.py`, update it; otherwise create it.

### Decision 7: Resolve `aspect_validation_guidance` collision explicitly

There are two differently shaped concepts:

- `app.assistant.aspect_metadata.aspect_validation_guidance(aspect)` returns metadata/guidance for one aspect.
- The graph-internal `_aspect_validation_guidance(required_aspects)` returns `dict[str, str]` for judge/prompt usage.

The compatibility shim exports the existing public `aspect_validation_guidance` from `app.assistant.aspect_metadata` under its original name. The graph-internal helper is renamed and exported as `_graph_aspect_validation_guidance` from `app.assistant.graph.answerability` and the shim.

Before implementation completes, grep must verify no caller expects the graph-internal dict-producing helper under the bare `aspect_validation_guidance` name.

### Decision 8: Do not introduce semantic keyword heuristics during the split

Any existing deterministic checks are moved as-is. New semantic behavior is not introduced. The split must not add keyword lists, language-specific word checks, substring routing, or regex language detection for plant-care meaning.

Deterministic code remains acceptable only for existing non-semantic boundaries such as schema validation, enum validation, trusted-domain checks, non-empty text checks, conservative fallback routing, and safety boundaries after model failure.

### Decision 9: Keep modules below 500 lines

The implementation should keep each `app/assistant/graph/*.py` module below 500 lines. If a module approaches the limit during extraction, split by ownership rather than relaxing the limit. The requested target layout gives the first ownership boundary; implementation may introduce a second small module only if necessary to meet the file-size constraint without obscuring ownership.

## Risks / Trade-offs

- **Risk: Import cycles between facade, topology, and helper modules.** → Mitigation: `types.py` and `constants.py` are leaf modules; submodules should import contracts from them rather than from `facade.py`. `topology.py` should use type-only imports guarded by `TYPE_CHECKING` where needed.
- **Risk: Tests patch shim exports and stop affecting implementation behavior.** → Mitigation: update monkeypatch targets to canonical submodule paths in the same change.
- **Risk: Accidental behavior drift while moving large method bodies.** → Mitigation: move code mechanically first, delegate from the facade, and avoid semantic edits. Run focused assistant tests after each extracted concern.
- **Risk: The compiled graph changes accidentally.** → Mitigation: add or update topology tests that assert graph nodes and routing behavior remain unchanged.
- **Risk: The `aspect_validation_guidance` name collision hides the wrong function.** → Mitigation: explicitly rename the graph-internal dict helper to `_graph_aspect_validation_guidance` and grep call sites before final verification.
- **Risk: File-size constraints force awkward splits.** → Mitigation: prioritize concern ownership; if a module exceeds 500 lines, split into a narrowly named helper module rather than combining unrelated code.
- **Trade-off: Re-export shims preserve compatibility but keep old paths alive.** → This is intentional for this change. Cleanup of old import paths can happen later after consumers have migrated.

## Migration Plan

1. Create `app/assistant/graph/` with empty package scaffolding and import-safe leaf modules (`types.py`, `constants.py`).
2. Move state and result contracts into `types.py`; update imports in the original module or shim to preserve public names.
3. Move constants into `constants.py`.
4. Extract pure helpers and logging helpers into `helpers.py`.
5. Extract classifier logic into `classifier.py` and delegate `AssistantGraph.classify_intent` to it.
6. Extract answerability logic into `answerability.py`, including the renamed `_graph_aspect_validation_guidance` helper.
7. Extract web evidence helpers into `web_evidence.py`.
8. Extract prompt builders into `prompts.py`.
9. Extract fallback drafts, answer generation, and answer cleanup into `answers.py`.
10. Extract safety helpers into `safety.py`.
11. Extract plant-resolution helpers into `plant_resolution.py`.
12. Extract routing predicates into `routes.py`.
13. Extract graph compilation and sequential fallback into `topology.py`.
14. Move `AssistantGraph` to `facade.py`; replace method bodies with one-line delegates.
15. Replace `app/assistant/graph.py` with a shim that re-exports the public and test-imported symbols from canonical modules.
16. Update tests to monkeypatch canonical module paths.
17. Verify no `app/assistant/graph/*.py` file exceeds 500 lines.
18. Run `ruff check` and the full test suite.

Rollback is straightforward because the change is source-only: revert the change commit to restore the monolithic module. No database, API, storage, or external dependency migration is involved.

## Open Questions

No blocking open questions remain. The implementation must verify via grep that no runtime caller relies on the graph-internal `aspect_validation_guidance` helper under the bare public name before finalizing the shim exports.
