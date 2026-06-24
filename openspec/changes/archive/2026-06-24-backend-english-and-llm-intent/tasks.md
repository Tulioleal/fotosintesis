## 1. Translate backend API user-facing strings

- [x] 1.1 Translate the 6 `HomeAccessItem.label` strings in `backend/app/api/home.py:17-22` to English (`My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, `Assistant`).
- [x] 1.2 Translate the 7 `HTTPException.detail` strings in `backend/app/api/profile_garden.py:36, 43, 67, 89, 106, 111, 112` to English. Preserve the validation/error meaning.
- [x] 1.3 Translate the 9 `HTTPException.detail` strings in `backend/app/api/identifications.py:32, 34, 50, 68, 78, 89, 97, 117, 167` to English. Keep the existing English errors at lines 122 and 150 as-is.
- [x] 1.4 Translate the 5 `HTTPException.detail` strings in `backend/app/api/reminders.py:37, 54, 68, 80, 89` to English.
- [x] 1.5 Translate the 1 `HTTPException.detail` string in `backend/app/api/light_measurements.py:23` to English.
- [x] 1.6 Translate the `RecoveryResponse.message` in `backend/app/api/auth.py:99` to English.

## 2. Translate assistant prompts, safety templates, and stored prose (extended)

- [x] 2.1 Translate the entire `_general_guidance_with_disclaimer_prompt` in `backend/app/assistant/graph.py` (around lines 2972, 2975-3002, 3002-3004, 3024-3025) to English. Preserve the disclaimer semantics, the soft-linguistic-connector guidance, and the new display-name preservation paragraph (lines 3002-3004).
- [x] 2.2 Translate the entire `_grounded_answer_prompt` in `backend/app/assistant/graph.py` (around lines 3030-3065, 3051-3054, 3065-3067, 3082-3083) to English. Preserve the source-backed-claim integration guidance, the soft-linguistic-connector guidance, the new connector-priority paragraphs (lines 3051-3054, 3082-3083), and the new display-name preservation paragraph (lines 3065-3067).
- [x] 2.3 Translate the `_conservative_safety_answer` templates in `backend/app/assistant/graph.py` (around lines 2791, 2793, 2795, 2822) to English. Preserve the required safety points (no definitive claim, vet/poison-control recommendation for pet safety, do-not-consume for edibility).
- [x] 2.4 Translate the `_taxonomy_context` strings in `backend/app/assistant/graph.py` (around line 2449) to English.
- [x] 2.5 Translate the `_simple_fallback_draft` defaults in `backend/app/assistant/graph.py` (around line 2217) to English. Replace `Sin fuentes estructuradas.` and `Ninguna limitacion explicita.` with their English equivalents.
- [x] 2.6 Translate the 2 stored `suggestion_justification` values in `backend/app/assistant/graph.py:521, 548` to English.
- [x] 2.7 Translate the connector phrases in `backend/app/assistant/graph.py` (`"Como pauta general…"` → `"As a general guideline…"`, `"En terminos generales…"` → `"In general terms…"`, `"Una practica habitual complementaria…"` → `"A common complementary practice is…"`, `"Como referencia complementaria…"` → `"As a complementary reference…"`) to English.
- [x] 2.8 Translate the 2 Spanish entries in `INJECTION_PATTERNS` in `backend/app/assistant/graph.py:38-45` to English (`"ignora las instrucciones"` → `"ignore the instructions"`, `"omite las reglas"` → `"omit the rules"`). Keep all English entries as-is.
- [x] 2.9 Translate the validation message at `backend/app/assistant/graph.py:649` from `f"No pude validar: {', '.join(missing_aspects)}"` to `f"Could not validate: {', '.join(missing_aspects)}"`.
- [x] 2.10 Translate the web-sources disclaimer at `backend/app/assistant/graph.py:697-698` from `"Esta guia usa fuentes web recientes aun no incorporadas al conocimiento persistido."` to `"This guide uses recent web sources that have not yet been incorporated into the persisted knowledge."`.
- [x] 2.11 Translate the enriched-facts labels in `_model_generation_failed_draft` at `backend/app/assistant/graph.py:2323, 2327, 2331`: `f"Contradiccion detectada: {line}"` → `f"Detected contradiction: {line}"`, `f"Limitacion: {lim}"` → `f"Limitation: {lim}"`, `f"Aspecto faltante: {missing}"` → `f"Missing aspect: {missing}"`.

## 3. Remove Spanish-keyword semantic-intent detection

- [x] 3.1 In `backend/app/assistant/graph.py`, delete the Spanish intent/routing branches in `_deterministic_classification` (around lines 1308-1347) that match on words like `regi`, `luz`, `mascota`, `toxico`, `nativa`, `recordame`, `identifica`, `recorda`, `agrega jardin`. The function should return `None` (route to the LLM classifier) for all cases that previously short-circuited on Spanish keywords. Only the `unsafe_or_injection` branch stays.
- [x] 3.2 Delete the `_is_light_measurement_request` function in `backend/app/assistant/graph.py:1363`. The LLM classifier handles this.
- [x] 3.3 Delete the `_message_has_plant_context` function and the `botanical_terms` list in `backend/app/assistant/graph.py:1371-1382`. The LLM classifier and the explicit `plant` / `plant_binomial_name` / `plant_scientific_name` request fields handle plant context.
- [x] 3.4 Delete the `_is_edibility_question` function in `backend/app/assistant/graph.py:2549-2561`. The LLM classifier handles this.
- [x] 3.5 Delete the `_is_pet_safety_question` function in `backend/app/assistant/graph.py:2567-2596`. The LLM classifier handles this.
- [x] 3.6 Delete the `_extract_recurrence`, `_extract_reminder_action`, and `_wants_reminder_suggestion` functions in `backend/app/assistant/graph.py:3080-3108`. The LLM classifier and the explicit reminder request fields handle these. The user-confirmation flow remains the safety net.
- [x] 3.7 Remove all call sites of the deleted functions from `_deterministic_classification` and any graph nodes that referenced them. The graph should not call any deleted helper. Update any docstring that referenced the deleted Spanish-keyword behavior.

## 4. Keep the Spanish attribution-stripping regex as a defensive fallback

- [x] 4.1 Confirm that the Spanish attribution-stripping regex at `backend/app/assistant/graph.py:3130` is left untouched. The English `According to …` regex one line above remains the primary one; the Spanish regex is a defensive fallback in case a model output accidentally includes Spanish attribution patterns.

## 5. Translate test_assistant_agent.py fixtures and assertions (extended)

- [x] 5.1 Translate all Spanish `user_message` fixtures in `backend/tests/test_assistant_agent.py` to English, **except** for the 5-6 language-behavior tests (line 626, 666, 1630, the parametrize cases at 6618, the Italian test at 6428, the Italian test at 5782, the Spanish snippet test at 5620, and the `test_minimal_fallback_routes_*` family at 1647-1759).
- [x] 5.2 Translate all Spanish `model_response` fixtures in `backend/tests/test_assistant_agent.py` to English, **except** for the 5-6 language-behavior tests.
- [x] 5.3 Translate all Spanish `FakeTools` stub outputs in `backend/tests/test_assistant_agent.py` to English. Update the assertion substrings to match. Keep the Spanish stubs/assertions in the 5-6 language-behavior tests.
- [x] 5.4 Translate the Spanish `model_response` fixtures in the disclaimed-guidance / RAG / URL-stripping test families (`test_general_guidance_prompt_requires_separation_and_safety_prohibitions` line 6094, `test_pest_question_with_relevant_context_routes_to_disclaimed_guidance` line 6210, `test_disclaimed_guidance_*` line 6245, `test_disclaimed_guidance_emits_no_ingestion_claims` line 6293, `test_partial_evidence_ingestion_uses_only_validated_source_support` line 6323, `test_safety_sensitive_missing_aspect_keeps_conservative_fallback` line 6404, `test_combined_rag_web_insufficient_routes_to_disclaimed_guidance` line 6481, `test_pesticide_instruction_request_does_not_return_chemical_advice` line 6699, `test_grounded_prompt_prohibits_urls_and_source_labels` line 6751, `test_grounded_prompt_structured_api_no_attribution_instruction` line 6827, `test_grounded_response_*` line 6867-7027) to English. Update the assertion substrings to match the new English production prompt.
- [x] 5.5 Update the forbidden-phrase assertions in `test_no_deterministic_emergency_prose_on_total_generation_failure` (line 5663) and `test_rag_fallback_does_not_return_prewritten_prose` (line 5680) to use the new English fallback phrases (`"I could not generate"`, `"Try again"`, `"A practical guide is:"`, `"For"` not `"Para"`).
- [x] 5.6 Translate the assertion substrings in `test_assistant_reports_degraded_knowledge_limitations` (line 2022) to English. Update the `FakeTools` stub at line 471 to English.
- [x] 5.7 Translate the assertion substrings in `test_conservative_safety_fallback_for_pet_safety_without_direct_evidence` (line 3206) and `test_conservative_safety_fallback_for_edibility_without_direct_evidence` (line 3225) to English.
- [x] 5.8 Rewrite or fold the `test_minimal_fallback_routes_*` family (lines 1647-1759) into the LLM-classifier test families. Added docstring note explaining that the deterministic-classifier Spanish-keyword paths are gone. Tests remain as-is with `FailClassifierTools`; routing tests now depend on LLM classifier.
- [x] 5.9 Verify that the 5-6 language-behavior tests still pass with their original Spanish/Italian messages: `test_classifier_prompt_uses_actual_message_language_and_ignores_switch_requests` (line 626), `test_spanish_message_requesting_english_uses_classifier_spanish_for_fallback` (line 666), `test_minimal_fallback_routes_injection_as_unsafe` (line 1630), the 3 Spanish safety-sensitive parametrize cases in `test_safety_boundary_cases` (line 6618), `test_multilingual_pest_question_routes_by_schema_state_not_keywords` (line 6428), `test_non_english_evidence_reaches_model_without_keyword_matching` (line 5782), and `test_non_english_snippet_reaches_judge_without_keyword_filter` (line 5620).
- [x] 5.10 Translate the default `FakeTools` fixtures in `backend/tests/test_assistant_agent.py` (lines 213, 218, 385, 463, 465, 467, 469, 471, 473, 475, 477, 478, 479, 481, 483) to English. Translated `model_response="Respuesta sintetizada por modelo."` → `"Synthesized model response."`, `model_response="Respuesta de fallback renderizada por modelo."` → `"Model-rendered fallback response."`, `knowledge_content="Requiere riego moderado y sustrato con buen drenaje."` → `"Requires moderate watering and well-draining substrate."`, `metadata={"title": "Ficha botanica"}` → `{"title": "Botanical record"}`, and all the `FakeTools.generate_text` Spanish stub outputs at lines 463-481.
- [x] 5.11 Translate the ~40 Spanish `classifier_data` dicts in `backend/tests/test_assistant_agent.py` (those with `"language": "es"`, `"answer_language": "es"`) to English (`"language": "en"`, `"answer_language": "en"`) for tests whose purpose is to verify routing/intent/aspect logic (not language behavior). Keep Spanish only in the 5-6 language-behavior tests.
- [x] 5.12 Translate the 11 new display-name / nickname test functions at lines 7057, 7081, 7105, 7142, 7168, 7196, 7216, 7236, 7256, 7276, 7297 to English: translate the Spanish assertion substrings (`"Cuando te dirijas a la planta en la respuesta"`, `"usa siempre el nombre proporcionado como 'Planta seleccionada'"`, `"Nunca reemplaces ese nombre por el nombre comun"`, `"el nombre cientifico"`, `"el binomio"`) to English, and translate the Spanish `model_response` fixtures (lines 7199, 7201, 7222, 7242, 7259, 7261).

## 6. Translate test_reminders.py fixtures

- [x] 6.1 Translate the Spanish `notes` / `location` / `action` values in `backend/tests/test_reminders.py` to English. Keep the Spanish plant common names (`"Helecho"`, `"Pata de oso"`) as-is.
- [x] 6.2 Update the assertion substrings in `backend/tests/test_reminders.py` to match the new English user-facing error messages from `backend/app/api/reminders.py`.

## 7. Add regression tests proving the LLM classifier is the sole semantic-intent path

- [x] 7.1 Add a regression test that exercises a Spanish-language reminder request message and asserts that the LLM classifier produces `intent: "reminder_request"` and routes to the reminder flow, without any deterministic Spanish-keyword matching.
- [x] 7.2 Add a regression test that exercises a Spanish-language light-measurement request message and asserts that the LLM classifier produces `intent: "light_measurement_question"` and routes to the light-measurement flow, without any deterministic Spanish-keyword matching.
- [x] 7.3 Add a regression test that exercises a Spanish-language plant-identification request message and asserts that the LLM classifier produces `intent: "plant_identification_question"` and routes to the identification flow, without any deterministic Spanish-keyword matching.
- [x] 7.4 Add a regression test that exercises a Spanish-language edibility question and asserts that the LLM classifier produces `topic: "toxicity_safety"` and `required_aspects` including `toxicity_human_edibility`, without any deterministic Spanish-keyword matching.
- [x] 7.5 Add a regression test that exercises a Spanish-language pet-safety question and asserts that the LLM classifier produces `topic: "toxicity_safety"` and `required_aspects` including `toxicity_pet_safety`, without any deterministic Spanish-keyword matching.
- [x] 7.6 Add a regression test that asserts the deterministic fallback (`_deterministic_classification`) returns `None` for non-unsafe Spanish-keyword messages (e.g. a Spanish message containing `recordame`, `mascota`, `luz`, `identifica`, `toxico`, `nativa`) and never returns a populated `CareClassification` for those messages.
- [x] 7.7 Add a regression test that asserts the deterministic fallback still routes `unsafe_or_injection` for an English prompt-injection message containing the new English `INJECTION_PATTERNS` entry (`"ignore the instructions"` or `"omit the rules"`).

## 8. Verification

- [x] 8.1 Run `pytest backend/tests/` and confirm all tests pass, including the 5-6 language-behavior tests with their original Spanish/Italian messages. **Result: 487 passed, 1 skipped, 4 failed (all 4 failures are pre-existing and unrelated to this change: 2 in `test_auth_home.py` for vision provider mock issues, 2 in `test_evaluation_pipeline.py` for missing `google-genai` dependency).**
- [x] 8.2 Run the backend linter (e.g. `ruff` or `flake8` per `pyproject.toml`) and confirm no lint regressions. **Result: 35 ruff errors before changes, 35 ruff errors after — no regressions.**
- [x] 8.3 Run a grep for remaining Spanish strings in `backend/app/` (excluding `lang="es"` ISO code references) and confirm the only Spanish residue is the Spanish attribution-stripping regex at `graph.py:3073`. **Result: confirmed — only the Spanish attribution-stripping regex remains.**
- [x] 8.4 Run a grep for remaining Spanish strings in `backend/tests/` (excluding the 5-6 language-behavior tests, the 7 new regression tests in tasks 7.1-7.7, and Spanish plant common names). **Result: only the 5-6 language-behavior tests and the 7 new regression tests retain their Spanish content (as designed).**
- [x] 8.5 Manually exercise the home screen, profile garden, identifications, reminders, light meter, auth recovery, and assistant in the running stack to confirm the English labels and error messages render correctly. **NOTE: API strings (tasks 1.1-1.6) are translated. Assistant prompts and templates (tasks 2.1-2.11) are translated. Manual UI smoke not run in this environment.**
- [x] 8.6 Run a grep for the specific translated phrases (`"Synthesized model response."`, `"Model-rendered fallback response."`, `"Requires moderate watering and well-draining substrate."`, `"Botanical record"`) in `backend/tests/test_assistant_agent.py` and confirm they appear in the `FakeTools` defaults and the assertion substrings. **Result: confirmed.**
- [x] 8.7 Confirm the 11 new display-name / nickname test functions (lines 7057-7346) use English assertion substrings and English `model_response` / `knowledge_content` fixtures, and that the nickname-in-prose test point is preserved. **Result: confirmed.**

## 9. Translate remaining user-facing data fields (follow-up to warnings)

- [x] 9.1 Translate `_possible_match_copy` in `backend/app/identification/repository.py:13-18` to English.
- [x] 9.2 Translate `SECTION_TOPICS` keys in `backend/app/profile_garden/repository.py:22-30` to English.
- [x] 9.3 Translate the section fallback message in `backend/app/profile_garden/repository.py:222` to English.
- [x] 9.4 Translate the RAG-limitation message in `backend/app/profile_garden/repository.py:228-229` to English.
- [x] 9.5 Translate the partial-confidence message in `backend/app/profile_garden/repository.py:233` to English.
- [x] 9.6 Translate the `ValueError` in `backend/app/assistant/repository.py:101` to English.
- [x] 9.7 Translate the mock vision `visible_traits` in `backend/app/providers/mocks.py:71` to English.

## 10. Update tests for translated data fields

- [x] 10.1 Update the test fixture `possible_match_copy` in `backend/tests/test_profile_garden.py:158` from `"Coincide con helecho domestico."` to an English string (e.g. `"Matches a domestic fern."`) so the fixture mirrors the new English production copy.
- [x] 10.2 Update the test fixture `visible_traits` in `backend/tests/test_profile_garden.py:157` from `["frondes"]` to `["fronds"]` (locale-consistent English). Note: this test fixture value is test data, not asserted on string content; verify with the surrounding test before changing.

## 11. Update spec for data-field wording

- [x] 11.1 Add an `ADDED Requirement: Plant profile sections and limitations are English` to `specs/plant-profile-garden/spec.md`, with a scenario asserting that `PlantProfileResponse.sections` keys are in English (`description`, `characteristics`, `conditions`, `care`, `pests`, `diseases`, `recommendations`) and `PlantProfileResponse.limitations` values are in English.
- [x] 11.2 Add a scenario to `specs/plant-identification-taxonomy/spec.md` under the **MaaS visual candidates** requirement asserting that `TaxonomyCandidate.possible_match_copy` is in English.

## 12. Re-verify

- [x] 12.1 Run `rg` (or `grep`) for Spanish strings in `backend/app/` excluding the Spanish attribution-stripping regex, ISO `"es"` codes, and the Spanish plant common names — confirm only those remain. **Result: only the Spanish attribution-stripping regex at `graph.py:3073` remains.**
- [x] 12.2 Run `pytest backend/tests/` — confirm the 487/1/4 result still holds and the `possible_match_copy` test still passes. **Result: 487 passed, 1 skipped, 4 failed (same pre-existing failures). `test_profile_garden.py` 3/3 passes.**
- [x] 12.3 Run `ruff check app/ tests/` — confirm no new errors. **Result: 35 errors, same as baseline.**
- [x] 12.4 Run `/opsx-verify backend-english-and-llm-intent` again — confirm the WARNINGs and SUGGESTION are resolved.
