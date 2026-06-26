## 1. Preparation and Baseline

- [x] 1.1 Run `grep -rn "aspect_validation_guidance" backend/app backend/tests --include="*.py"` and record whether any runtime caller depends on the graph-internal dict-producing helper under the bare name.
- [x] 1.2 Run the current assistant graph tests to establish a baseline before moving code.
- [x] 1.3 Inspect current `tests/test_assistant_agent.py` monkeypatch targets that point at `app.assistant.graph.<symbol>` and group them by target submodule.
- [x] 1.4 Inspect or create `tests/test_graph_topology.py` coverage that can detect changes to assistant graph nodes and route behavior.

## 2. Create Graph Package Skeleton

- [x] 2.1 Expose `backend/app/assistant/graph/` as the shim-backed namespace used by `backend/app/assistant/graph.py` for canonical submodule imports; keep the namespace package design instead of adding `__init__.py`.
- [x] 2.2 Create empty concern modules: `types.py`, `constants.py`, `helpers.py`, `classifier.py`, `answerability.py`, `web_evidence.py`, `answers.py`, `prompts.py`, `safety.py`, `plant_resolution.py`, `routes.py`, `topology.py`, and `facade.py`.
- [x] 2.3 Keep `backend/app/assistant/graph.py` in place as the thin shim while moving symbols mechanically and preserving existing imports/tests.

## 3. Move Shared Contracts and Constants

- [x] 3.1 Move `FallbackResponseDraft`, `AssistantState`, and `AnswerabilityResult` into `app.assistant.graph.types`.
- [x] 3.2 Move `PLANT_CONTEXT_HINTS`, `INJECTION_PATTERNS`, and `LEGACY_ASPECT_TRANSLATION` into `app.assistant.graph.constants`.
- [x] 3.3 Update graph imports so moved state/result contracts and constants resolve from the new canonical modules.
- [x] 3.4 Verify `from app.assistant.graph.types import AssistantState, FallbackResponseDraft, AnswerabilityResult` works.

## 4. Move Helpers and Classifier Logic

- [x] 4.1 Move pure coercion helpers and shared logging helpers into `app.assistant.graph.helpers`.
- [x] 4.2 Move `_classify_care_message`, `_classifier_retry_once`, `_log_classifier_invalid_output`, `_truncate_for_log`, `_care_classifier_prompt`, `_care_classifier_repair_prompt`, `_care_classifier_response_template`, `_extract_missing_field_names`, `_field_name_present_in_text`, `_deterministic_classification`, and `_legacy_intent_from_care_intent` into `app.assistant.graph.classifier`.
- [x] 4.3 Extract `AssistantGraph.classify_intent` body into a module-level delegate in `app.assistant.graph.classifier`.
- [x] 4.4 Update `AssistantGraph.classify_intent` to call the classifier delegate as a one-liner.
- [x] 4.5 Run classifier-related assistant tests and fix imports without changing classification semantics.

## 5. Move Answerability and Web Evidence Logic

- [x] 5.1 Move answerability conversion, validation, status, source-support, contradiction, combined-evidence, diagnostic, and recoverable-failure helpers into `app.assistant.graph.answerability`.
- [x] 5.2 Rename the graph-internal `_aspect_validation_guidance` helper to `_graph_aspect_validation_guidance` and keep it in `app.assistant.graph.answerability`.
- [x] 5.3 Move `_requested_web_aspects`, `_final_required_aspect_values`, `_combined_answer_evidence`, `_supported_rag_evidence`, `_web_source_validation_metadata_from_result`, `_source_support_urls`, `_required_aspects_from_state`, `_is_strong_full_support`, and `_validation_threshold_for_aspect` to their canonical answerability or web-evidence modules based on ownership.
- [x] 5.4 Move `_targeted_web_query`, `_reusable_web_search_candidates`, `_candidate_results_from_web_data`, `_web_query_question_context`, `_validated_web_metadata`, `_validated_claim_payloads`, `_sources_from_retrieval`, `_sources_from_web_results`, `_sources_from_structured_evidence`, `_usable_web_results`, `_with_evidence_lengths`, and `_snippet_has_content` into `app.assistant.graph.web_evidence`.
- [x] 5.5 Extract `AssistantGraph.evaluate_sufficiency` and `AssistantGraph.fallback_web_search` bodies into delegates in the owning submodules.
- [x] 5.6 Update facade methods to call answerability and web-evidence delegates as one-liners.
- [x] 5.7 Run answerability, evidence validation, and web fallback tests without adding keyword, translation-list, substring, or language-specific semantic heuristics.

## 6. Move Answer Generation, Prompts, Safety, and Plant Resolution

- [x] 6.1 Move `_general_guidance_with_disclaimer_prompt` and `_grounded_answer_prompt` into `app.assistant.graph.prompts`.
- [x] 6.2 Move fallback drafts, fallback response prompts, recovery drafts, model-generation-failed drafts, conservative safety answer generation, structured/web/grounded/disclaimed generation, and source-attribution cleanup into `app.assistant.graph.answers`.
- [x] 6.3 Move `_is_safety_sensitive_question`, `_has_missing_safety_aspect`, `_has_requested_safety_aspect`, and `_has_relevant_plant_context` into `app.assistant.graph.safety`.
- [x] 6.4 Move `operational_plant_name`, `display_plant_name`, `_first_non_blank`, `_normalize_plant_name`, `_binomial_from_scientific_name`, `_operational_name_for_tools`, `_display_name_for_answer`, `_has_confirmed_taxonomy_context`, `_taxonomy_context`, `_select_plant`, `_message_confirms_selected_plant`, and `_display_plant` into `app.assistant.graph.plant_resolution`.
- [x] 6.5 Extract `AssistantGraph.load_user_context`, `AssistantGraph.retrieve`, `AssistantGraph.fallback_plant_data`, `AssistantGraph.handle_action`, `AssistantGraph._handle_reminder`, `AssistantGraph.clarify`, `AssistantGraph.generate_answer`, `AssistantGraph._generate_structured_answer`, `AssistantGraph._generate_web_answer`, `AssistantGraph._generate_disclaimed_guidance`, `AssistantGraph._generate_grounded_answer`, `AssistantGraph._generate_fallback_response`, and `AssistantGraph.failure` bodies into owning submodule delegates.
- [x] 6.6 Update facade methods to call the new delegates as one-liners.
- [x] 6.7 Run assistant answer-generation, safety, plant-resolution, reminder, and fallback tests without changing runtime behavior.

## 7. Move Routes and Topology

- [x] 7.1 Move `_is_disclaimed_guidance_eligible`, `_route_after_context`, `_route_after_sufficiency`, `_route_after_web_fallback`, and `_route_after_failure` into `app.assistant.graph.routes`.
- [x] 7.2 Do not reintroduce `_route_after_plant_data_fallback` unless implementation proves it is still required by the current topology.
- [x] 7.3 Move `_compile_graph` and `_SequentialGraph` into `app.assistant.graph.topology`.
- [x] 7.4 Update `AssistantGraph.__init__` to compile through `app.assistant.graph.topology._compile_graph`.
- [x] 7.5 Update or add topology tests proving compiled graph nodes and route behavior remain unchanged.

## 8. Replace Monolithic Module with Shim

- [x] 8.1 Move the final `AssistantGraph` class implementation into `app.assistant.graph.facade`.
- [x] 8.2 Replace `backend/app/assistant/graph.py` with a thin re-export shim for `AssistantGraph`, `AssistantState`, `FallbackResponseDraft`, `AnswerabilityResult`, existing public helpers, and test-imported private helpers.
- [x] 8.3 Export the public `aspect_validation_guidance` name from `app.assistant.aspect_metadata` through the shim.
- [x] 8.4 Export `_graph_aspect_validation_guidance` from the shim for graph-internal dict guidance compatibility.
- [x] 8.5 Verify `from app.assistant.graph import X` still works for all symbols imported by production code and tests.

## 9. Update Tests to Canonical Patch Targets

- [x] 9.1 Rewrite answerability monkeypatch targets from `app.assistant.graph.<symbol>` to `app.assistant.graph.answerability.<symbol>`.
- [x] 9.2 Rewrite prompt monkeypatch targets from `app.assistant.graph.<symbol>` to `app.assistant.graph.prompts.<symbol>` or confirm none remain.
- [x] 9.3 Rewrite web evidence monkeypatch targets from `app.assistant.graph.<symbol>` to `app.assistant.graph.web_evidence.<symbol>` or confirm none remain.
- [x] 9.4 Rewrite classifier monkeypatch targets from `app.assistant.graph.<symbol>` to `app.assistant.graph.classifier.<symbol>` or confirm none remain.
- [x] 9.5 Rewrite route/topology monkeypatch targets from `app.assistant.graph.<symbol>` to `app.assistant.graph.routes.<symbol>` or `app.assistant.graph.topology.<symbol>`, or confirm none remain.
- [x] 9.6 Preserve regression coverage proving non-English, synonym, or paraphrased botanical evidence still reaches schema-validated classifier and semantic answerability judging without keyword-match shortcuts.

## 10. Verification

- [x] 10.1 Run `python -m compileall backend/app/assistant` or the project-equivalent import check to catch circular imports.
- [x] 10.2 Run `ruff check backend/app backend/tests`.
- [x] 10.3 Run assistant-focused tests, including the split `tests/test_assistant_agent_part*.py` files and `tests/test_graph_topology.py`.
- [x] 10.4 Run the full backend test suite.
- [x] 10.5 Verify every `backend/app/assistant/graph/*.py` module is under 500 lines.
- [x] 10.6 Verify `backend/app/assistant/graph.py` is a small shim with no business logic.
- [x] 10.7 Verify no new deterministic keyword lists, translated word lists, substring checks, or language-specific heuristics were added for semantic plant-care behavior.
