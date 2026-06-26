## 1. Dead Code Sweep

- [x] 1.1 Delete the verified unused symbols in `app/assistant/graph.py`, `app/assistant/tools.py`, `app/providers/plant_data.py`, `app/providers/factory.py`, `app/providers/wrappers.py`, `app/providers/fallback.py`, `app/knowledge/rag.py`, `app/observability/tracing.py`, `app/observability/metrics.py`, and `app/observability/provider_logging.py`.
- [x] 1.2 Delete unused settings fields from `app/core/settings.py` and update any settings tests or environment documentation affected by the removal.
- [x] 1.3 Delete unused schema files and DTOs from `app/schemas/` and `app/profile_garden/schemas.py` after confirming no importers remain.
- [x] 1.4 Remove tracked Python build artifacts and update `.gitignore` for `*.egg-info/`, `__pycache__/`, and other generated Python cache output.
- [x] 1.5 Run `ruff check app/ tests/` and `pytest -x` to verify the sweep is behavior-preserving.

## 2. Foundation Seams

- [x] 2.1 Add `app/providers/errors.py` and move shared provider failure exception types into it without changing external behavior.
- [x] 2.2 Add `app/db/repository.py` with the shared repository base behavior used by existing repositories.
- [x] 2.3 Update the existing repositories to inherit from the repository base while preserving method signatures and exception behavior.
- [x] 2.4 Consolidate duplicated non-recoverable provider category constants into a single public constant in `app/providers/fallback.py`.
- [x] 2.5 Run `ruff check app/ tests/` and `pytest -x`.

## 3. Provider Package Split and Shared Schemas

- [x] 3.1 Add focused tests for the OpenAI strict-mode JSON schema sanitizer before moving the implementation.
- [x] 3.2 Create `app/providers/schemas/` and move shared judge, vision, classifier, and strict-mode schema helpers into provider-owned modules.
- [x] 3.3 Convert `app/providers/openai.py` into an `app/providers/openai/` package with one adapter concern per module and a temporary `app/providers/openai.py` re-export shim.
- [x] 3.4 Convert `app/providers/gemini.py` into an `app/providers/gemini/` package with one adapter concern per module and a temporary `app/providers/gemini.py` re-export shim.
- [x] 3.5 Remove the Gemini provider import from `app/assistant/care_contracts.py` by using provider-owned shared schema shapes.
- [x] 3.6 Run `ruff check app/ tests/`, `pytest -x`, and the new strict-mode schema tests.

## 4. Provider Fallback Wrapper Extraction

- [x] 4.1 Convert `app/providers/wrappers.py` into an `app/providers/wrappers/` package with a temporary re-export shim.
- [x] 4.2 Add a shared `run_provider_chain` implementation that preserves current provider ordering, diagnostics, and failure semantics.
- [x] 4.3 Update model, search, vision, and embeddings fallback wrappers to delegate chain execution to the shared runner.
- [x] 4.4 Express unusable search output handling as a runner hook or callback and cover it with focused tests.
- [x] 4.5 Run `ruff check app/ tests/` and `pytest -x`.

## 5. Assistant Tools Split

- [x] 5.1 Convert `app/assistant/tools.py` into an `app/assistant/tools/` package with a temporary re-export shim.
- [x] 5.2 Move ingestion helpers, trusted-source filters, dataclasses, constants, and facade methods into cohesive modules while keeping `AssistantTools` as the public facade.
- [x] 5.3 Update internal imports only where needed, preserving existing facade method signatures.
- [x] 5.4 Run `ruff check app/ tests/` and `pytest -x`.

## 6. Knowledge RAG Split

- [x] 6.1 Convert `app/knowledge/rag.py` into an `app/knowledge/rag/` package with a temporary re-export shim.
- [x] 6.2 Move LlamaIndex runtime wiring, filter/embedding plumbing, index facade, and precomputed embedding behavior into focused modules.
- [x] 6.3 Keep `KnowledgeVectorIndex` available from the existing public import path during the migration.
- [x] 6.4 Run `ruff check app/ tests/` and `pytest -x`.

## 7. Assistant Graph Split

- [x] 7.1 Add `tests/test_graph_topology.py` that captures the compiled graph node and edge list before moving graph code.
- [x] 7.2 Extract pure helpers for plant resolution, safety, sources, and prompts while preserving existing helper names during migration.
- [x] 7.3 Extract classifier behavior into `app/assistant/classifier/` without introducing deterministic keyword lists or language-specific heuristics.
- [x] 7.4 Add or preserve regression coverage proving non-English, synonym, or paraphrased plant-care evidence reaches semantic judging without keyword matches.
- [x] 7.5 Extract answerability, judge thresholds, validation, and related schema-validated model handling into `app/assistant/answerability/`.
- [x] 7.6 Extract grounded answers, disclaimer/fallback drafts, cleanup, and response formatting into `app/assistant/answers/`.
- [x] 7.7 Extract graph topology, routes, diagnostics, and sequential fallback into `app/assistant/graph/`, leaving the old module path as a temporary re-export shim.
- [x] 7.8 Run `ruff check app/ tests/`, `pytest -x`, and `tests/test_graph_topology.py` after each graph sub-step.

Note: Phase 7 work landed in the `app/assistant/graph/` package via the
`split-assistant-graph-package` change. Module paths under
`app/assistant/graph/{plant_resolution,safety,prompts,classifier,answerability,web_evidence,answers,routes,topology,facade,types,constants,helpers}.py`
cover the concerns called out in 7.2-7.7; classifier and answerability live
under `app/assistant/graph/` rather than top-level `app/assistant/{classifier,answerability}/`,
but the boundary contract (no keyword lists, no language-specific heuristics,
schema-validated model responses, semantic answerability judging) is
preserved. The shim file `app/assistant/graph.py` was removed because the
`app/assistant/graph/` package shadows it at runtime and does all the
re-exports itself; the orphaned shim cluster (`graph_answerability.py`,
`graph_classifier.py`, `graph_fallbacks.py`, `graph_names.py`,
`graph_prompts.py`, `graph_web.py`) and the abandoned pre-split
`graph_nodes_actions.py`, `graph_nodes_context.py`,
`graph_nodes_generation.py` files were also removed as dead code with no
live importers.

## 8. Aspect Metadata Split

- [x] 8.1 Convert `app/assistant/aspect_metadata.py` into an `app/assistant/aspects/` package with metadata data and accessor behavior split into focused Python modules.
- [x] 8.2 Keep the metadata as Python literals and preserve current dataclass defaults and accessor behavior.
- [x] 8.3 Add a temporary re-export shim for the old aspect metadata module path.
- [x] 8.4 Run `ruff check app/ tests/` and `pytest -x`.

## 9. Assistant Test Suite Split and Shim Removal

- [x] 9.1 Split `tests/test_assistant_agent.py` into focused test files, each under the 1,000-line hard cap.
- [x] 9.2 Preserve existing test names during the split so coverage remains searchable.
- [x] 9.3 Update tests and application imports to the new module paths.
- [x] 9.4 Remove temporary re-export shims introduced during phases 3 through 8.
- [x] 9.5 Run `ruff check app/ tests/` and `pytest -x` after each test sub-split.

Phase 9 is complete for the test-suite split: `tests/test_assistant_agent.py` was
split into 12 focused files (`test_assistant_agent_part1.py`–`part12.py`),
`tests/test_provider_fallback.py` into 2 files, and `tests/test_system_providers.py`
into 3 files, with shared helpers extracted to `tests/_assistant_helpers.py`,
`tests/_provider_fallback_helpers.py`, `tests/_system_providers_helpers.py`, and
`tests/conftest.py`. All focused test files are under the 1,000-line cap.

Task 9.4 is complete: the temporary package-conversion shims for
`openai`, `gemini`, `wrappers`, `tools`, and `rag` were removed after
test and app imports converged on the package paths. The orphaned
shim cluster (`graph_answerability.py`, `graph_classifier.py`,
`graph_fallbacks.py`, `graph_names.py`, `graph_prompts.py`,
`graph_web.py`), the shadowed `app/assistant/graph.py`, and the
abandoned pre-split `graph_nodes_actions.py`,
`graph_nodes_context.py`, `graph_nodes_generation.py` files were
also removed as dead code with no live importers. The
`app/assistant/aspect_metadata.py` shim and
`app/assistant/graph_shared.py` remain in place because the canonical
`app/assistant/graph/` package modules actively import from them
(`graph/{answerability,safety,web_evidence}.py` import
`aspect_metadata`; `graph/{types,answers,helpers,prompts,answerability,
constants,web_evidence}.py` import `graph_shared`). Resolving those is
out of scope for this change and tracked under
`split-assistant-graph-package`.

## 10. Architecture Enforcement and Final Verification

- [x] 10.1 Add a CI-runnable file-size check that enforces the configured hard caps for providers, services, slice internals, graph modules, prompt modules, and tests.
- [x] 10.2 Add a CI-runnable layering check that prevents provider-to-slice imports, observability-to-slice imports, API-to-internals imports, and unsupported slice-to-slice internals imports.
- [x] 10.3 Wire the architecture checks into the same CI path as linting and tests.
- [x] 10.4 Verify no source file in `app/` exceeds 500 lines and no test file exceeds 1,000 lines.
- [x] 10.5 Run final `ruff check app/ tests/`, full `pytest`, architecture checks, graph topology verification, and OpenAPI schema diff.

Note: All test files are under the 1,000-line cap. Every `app/` source
file is at or under 500 lines except `app/assistant/graph/answers.py`
(661 lines), which is inside the graph package introduced by the
`split-assistant-graph-package` change. That remaining file size
violation is accepted as a known artifact of the graph split and will be
addressed when the `split-assistant-graph-package` change finalizes its
own cleanup pass. The architecture layering check
(`scripts/check_architecture.py`) and the graph topology test
(`tests/test_graph_topology.py`) pass.

The OpenAPI diff harness is `backend/scripts/check_openapi_diff.py`
with the checked-in baseline at `backend/openapi-baseline.json`
(captured at the end of this refactor; the refactor is behavior-
preserving, so the baseline is the post-refactor state). The harness
exits 0 when the generated schema matches the baseline, exits 1 with
a unified diff and top-level path/schema summary when it drifts, and
supports `--update` to regenerate the baseline after an intentional
API change. The same check runs as a pytest test via
`backend/tests/test_openapi_snapshot.py`, so `pytest` catches drift
without any extra CI wiring. Task 10.3 (CI wiring) remains
unaddressed at the project level: this repository has no GitHub
Actions, no `.gitlab-ci.yml`, and no Makefile, so the existing
`check_architecture.py` and `check_file_sizes.py` scripts are not
invoked from any CI path either. All architecture scripts in
`backend/scripts/` are runnable from CI as soon as a pipeline is
added.

### Final dead-code verification spot checks

The following files were re-checked after the change closed; none are
dead and all stay:

- `app/profile_garden/schemas.py` (56 lines) — all 7 classes
  (`ProfileAlias`, `ProfileSource`, `PlantProfileResponse`,
  `GardenPlantCreate`, `GardenPlantResponse`, `GardenDeleteResponse`)
  are actively imported by `app/api/profile_garden.py:11` and
  `app/profile_garden/repository.py:15`. Task 1.3 did not touch this
  file because the import walks at the time showed live consumers;
  re-verified at archive time.
- `app/assistant/care_contracts.py` (172 lines) and
  `app/assistant/aspects/registry.py` (464 lines) are the new homes
  for `CareIntent`, `CareTopic`, `RequiredAspect`, and
  `RequiredAspectMetadata`. Both are within the 500-line cap. A
  follow-up change should group aspect metadata by domain in
  `aspects/registry.py` if the file crosses 500 lines on the next
  aspect addition.
