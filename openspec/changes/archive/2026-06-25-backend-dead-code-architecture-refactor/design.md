## Context

The backend currently concentrates several unrelated responsibilities in oversized modules, most notably `app/assistant/graph.py`, `app/providers/openai.py`, `app/providers/gemini.py`, `app/providers/wrappers.py`, `app/assistant/aspect_metadata.py`, `app/assistant/tools.py`, and `app/knowledge/rag.py`. The largest assistant integration test file mirrors that coupling by reaching into many private helpers.

The refactor is intentionally behavior-preserving. It removes verified dead code, moves code into capability-focused packages, and adds architecture checks so future changes cannot recreate the same god-file and cross-layer dependency patterns. Existing multilingual botanical behavior remains model/schema/judge/evidence driven; deterministic code is limited to structural validation, provider selection, trusted-source checks, non-empty checks, and conservative fallback routing after model failure.

## Goals / Non-Goals

**Goals:**

- Delete verified unused code and tracked build artifacts in a low-risk first phase.
- Split every backend source file above the target size limit into cohesive capability modules.
- Remove the provider-to-assistant import by placing shared provider schema shapes in the provider layer.
- Consolidate duplicated provider fallback control flow behind one chain runner with explicit hooks for unusable results.
- Preserve public imports during migration with temporary re-export shims, then remove those shims once tests target the new module paths.
- Keep the compiled LangGraph topology, OpenAPI schema, provider selection behavior, and runtime assistant behavior unchanged.
- Add CI checks for file-size caps and layering boundaries.

**Non-Goals:**

- Changing HTTP routes, request schemas, response schemas, or OpenAPI output.
- Changing LangGraph node/edge behavior or runtime provider/model selection.
- Introducing a dependency-injection container.
- Adding new plant-care features or changing multilingual semantic classification, retrieval eligibility, evidence validation, answerability, or language handling behavior.
- Replacing source-grounded semantic checks with hardcoded keyword lists, translated word lists, regex language detection, or English/Spanish-specific heuristics.

## Decisions

### Use a pragmatic hybrid module layout

The backend keeps the current domain slices but splits heavy slices internally by capability. `app/assistant/` gains packages for graph orchestration, classifier behavior, answerability, answers, safety, prompts, sources, plant resolution, aspects, and tools. `app/providers/` becomes the explicit port/adapter boundary, with provider packages and shared provider schemas. `app/knowledge/rag.py` becomes a package while preserving the `KnowledgeVectorIndex` import surface.

Alternatives considered: a pure clean architecture rewrite would add indirection without a second implementation for most repositories; a pure vertical-slice-only approach would not solve the oversized internal assistant and provider modules.

### Preserve imports with temporary re-export shims

For package conversions, the old module path remains as a thin re-export shim during the migration. This keeps existing application imports and the large assistant test file compiling while implementation moves happen in smaller phases.

Alternatives considered: hard module cuts would make each phase larger and increase test churn; moving tests first would force test imports to point at modules that do not exist yet.

### Move shared provider schemas below `app/providers/`

Shared **semantic** schema fragments and value vocabularies (the
`covered_aspects`/`missing_aspects` enum of valid aspect values, the
`ProviderCareIntent` classifier intent vocabulary, and the OpenAI strict-mode
formatting helpers) move into `app/providers/schemas/`. Provider adapters then
format these shared semantic fragments into their own wire-format JSON schemas
in their per-provider package.

Provider-local wire-format schemas (for example, the per-provider `JUDGE_SCHEMA`
and `VISION_SCHEMA` dicts that must follow OpenAI strict-mode rules or Gemini
schema constraints) live in the per-provider package, not in
`app/providers/schemas/`. Only semantic fragments and enums that are reused by
more than one provider — or that are referenced from outside the provider layer
— must live in `app/providers/schemas/`. The current state satisfies this: the
`PROVIDER_REQUIRED_ASPECT_VALUES` enum and the `covered_aspects_array_schema`
helper are in `app/providers/schemas/shared_shapes.py` and are used by the
Gemini adapter; the OpenAI adapter intentionally uses free-form string arrays
in its wire schema and validates values downstream against the same shared
vocabulary.

This removes the previous provider import from `app/assistant/care_contracts.py`
and keeps providers independent from assistant internals.

Alternatives considered: duplicating schema definitions in each provider would
preserve the layering issue in another form and increase divergence risk;
centralizing every wire-format schema in `app/providers/schemas/` would couple
strict-mode and Gemini-specific constraints into a module that is supposed to
be provider-agnostic.

### Consolidate fallback wrappers behind one chain runner

The four provider fallback wrappers become thin delegates to a shared `run_provider_chain` runner. The existing unusable-search-output path becomes an explicit callback/hook instead of a one-off branch.

Alternatives considered: keeping four separate loop implementations avoids the extraction risk but preserves duplicated behavior and makes future fallback changes error-prone.

### Add architecture checks after the structural move

File-size and layering checks land after modules have been split enough to satisfy the caps. The check can be a lightweight AST/script-based CI step integrated with the existing lint/test job.

Alternatives considered: adopting a larger import-linter configuration is viable, but a small repository-specific script is sufficient for the stated boundaries and keeps dependencies unchanged.

## Risks / Trade-offs

- Deleting a symbol that is indirectly referenced -> Mitigation: delete only verified dead code, run `ruff check app/ tests/` and `pytest -x`, and keep deletions isolated in the first phase.
- Moving strict-mode JSON schema sanitizer code changes behavior -> Mitigation: add focused tests for sanitizer branches before moving it.
- Consolidating fallback wrappers changes provider failure semantics -> Mitigation: extract the shared runner first while preserving wrapper APIs, then remove duplicated loops only after tests pass.
- Splitting `graph.py` changes LangGraph topology -> Mitigation: add a graph topology test before the split and keep node/edge output stable through every graph sub-phase.
- Re-export shims temporarily obscure final module ownership -> Mitigation: track shim removal as an explicit late-phase task after tests have moved to the new paths.
- Splitting the large assistant test file loses coverage -> Mitigation: preserve test names during the split and run the suite after each sub-split.

## Migration Plan

1. Delete verified dead code, unused schema files, and tracked build artifacts; update `.gitignore`.
2. Add provider error types, repository base behavior, and shared fallback constants.
3. Convert OpenAI and Gemini provider modules into packages, extract strict-mode schema formatting and shared provider schemas, and remove the provider-to-assistant import.
4. Convert provider wrappers into a package and introduce the shared fallback chain runner.
5. Split assistant tools into a package while retaining the `AssistantTools` facade.
6. Split knowledge RAG into a package while retaining existing public imports.
7. Split assistant graph behavior in staged sub-steps, adding topology protection before the move.
8. Split aspect metadata into a small Python package.
9. Split the assistant integration test file and update test imports to new module paths; remove temporary re-export shims.
10. Add CI checks for file-size caps and layering rules, then run final verification including lint, tests, file-size checks, graph topology, and OpenAPI diff.

Rollback is phase-based: each phase is independently shippable and can be reverted without requiring later phases. During phases with re-export shims, rollback risk is lower because the old import paths remain available.

## Open Questions

- The exact CI integration point for the architecture script depends on the existing pipeline layout and should be chosen during implementation.
- The final module names inside the new assistant sub-packages may adjust slightly during extraction, but public behavior and phase boundaries remain fixed.
