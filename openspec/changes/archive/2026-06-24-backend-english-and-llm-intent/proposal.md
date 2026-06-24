## Why

The `backend/` codebase currently ships with Spanish as the de facto working language across three categories: (1) user-facing strings (UI labels, `HTTPException.detail` messages, recovery messages), (2) the assistant's LLM prompt and the conservative-safety answer templates, and (3) several Spanish keyword detection lists inside `app/assistant/graph.py`. The repo's `openspec/config.yaml` explicitly forbids translated word lists and English/Spanish-only heuristics for semantic plant-care behavior, and the standing rule is that the codebase should be English unless another language is explicitly needed for testing.

This change moves all production code, comments, prompts, and incidental test fixtures to English, removes the semantic-intent Spanish keyword detection paths (delegating them to the existing multilingual LLM classifier), keeps the few regression tests that exist specifically for language behavior in their original language, and leaves locale-specific plant common names untouched. After this change, the only Spanish residue in `backend/` is intentional language-behavior test coverage.

## What Changes

**Production code — translate to English (extended)**

- `backend/app/api/home.py:17-22` — translate the 6 `HomeAccessItem.label` strings (`Mi Jardín` → `My Garden`, `Identificar planta` → `Identify plant`, `Buscar plantas` → `Search plants`, `Medidor de luz` → `Light meter`, `Recordatorios` → `Reminders`, `Asistente` → `Assistant`).
- `backend/app/api/profile_garden.py:36, 43, 67, 89, 106, 111, 112` — translate 7 `HTTPException.detail` strings.
- `backend/app/api/identifications.py:32, 34, 50, 68, 78, 89, 97, 117, 167` — translate 9 `HTTPException.detail` strings (the file already has English errors at lines 122, 150 — those stay).
- `backend/app/api/reminders.py:37, 54, 68, 80, 89` — translate 5 `HTTPException.detail` strings.
- `backend/app/api/light_measurements.py:23` — translate 1 `HTTPException.detail` string.
- `backend/app/api/auth.py:99` — translate the recovery `RecoveryResponse.message`.
- `backend/app/assistant/graph.py:521, 548` — translate the 2 stored `suggestion_justification` values.
- `backend/app/assistant/graph.py:649` — translate `f"No pude validar: {', '.join(missing_aspects)}"` to `f"Could not validate: {', '.join(missing_aspects)}"`.
- `backend/app/assistant/graph.py:697-698` — translate `"Esta guia usa fuentes web recientes aun no incorporadas al conocimiento persistido."` to `"This guide uses recent web sources that have not yet been incorporated into the persisted knowledge."`.
- `backend/app/assistant/graph.py:2323, 2327, 2331` — translate the enriched-facts labels in `_model_generation_failed_draft`: `f"Contradiccion detectada: {line}"` → `f"Detected contradiction: {line}"`, `f"Limitacion: {lim}"` → `f"Limitation: {lim}"`, `f"Aspecto faltante: {missing}"` → `f"Missing aspect: {missing}"`.
- `backend/app/assistant/graph.py:2451-2459, 2217, 2352, 2449, 2791, 2793, 2795, 2822, 2972, 2975-3002, 3002-3004, 3024-3025, 3030-3065, 3065-3067, 3051-3054, 3082-3083` — translate the entire `_general_guidance_with_disclaimer_prompt` and `_grounded_answer_prompt` system prompts, the `_conservative_safety_answer` templates, the `_taxonomy_context` strings, the `_simple_fallback_draft` defaults, the `Sin fuentes estructuradas.` / `Ninguna limitacion explicita.` / `esta planta` defaults, **including the new display-name preservation paragraphs (lines 3002-3004 and 3065-3067) and the new connector-priority paragraphs (lines 3051-3054, 3082-3083)**. Translate the connector phrases (`"Como pauta general…"`, `"En terminos generales…"`, `"Una practica habitual complementaria…"`, `"Como referencia complementaria…"`) to their English equivalents.
- `backend/app/assistant/graph.py:3130` — keep the Spanish attribution-stripping regex as a defensive fallback (the LLM is now instructed to write in English, but defensive code is OK; the English regex one line above is the primary one).
- `backend/app/assistant/graph.py:38-45` — translate the Spanish entries in `INJECTION_PATTERNS` (`"ignora las instrucciones"` → `"ignore the instructions"`, `"omite las reglas"` → `"omit the rules"`). `INJECTION_PATTERNS` is a non-semantic safety boundary, so this is allowed by `openspec/config.yaml`.

**Production code — remove Spanish semantic-intent keyword detection**

- `backend/app/assistant/graph.py:1308-1347` (`_deterministic_classification`) — keep as a non-semantic conservative-fallback routing path (allowed by `openspec/config.yaml` for "conservative fallback routing after model failure"). Delete the Spanish intent/routing branches that match on words like `regi`, `luz`, `mascota`, `toxico`, `nativa`, `recordame`, `identifica`, `recorda`, `agrega jardin`. The function should return `None` (route to the LLM classifier) for all cases that previously short-circuited on Spanish keywords. Only the `unsafe_or_injection` branch stays.
- `backend/app/assistant/graph.py:1363` (`_is_light_measurement_request`) — delete the function. The LLM classifier handles this.
- `backend/app/assistant/graph.py:1371-1382` (`_message_has_plant_context` and `botanical_terms`) — delete. The LLM classifier + the explicit `plant` / `plant_binomial_name` / `plant_scientific_name` request fields handle plant context.
- `backend/app/assistant/graph.py:2549-2561` (`_is_edibility_question`) — delete. The LLM classifier handles this.
- `backend/app/assistant/graph.py:2567-2596` (`_is_pet_safety_question`) — delete. The LLM classifier handles this.
- `backend/app/assistant/graph.py:3080-3108` (`_extract_recurrence`, `_extract_reminder_action`, `_wants_reminder_suggestion`) — delete. These are semantic-intent detections and belong in the LLM classifier. The assistant already asks the user to confirm before creating a reminder, so the regression risk is bounded by the existing confirmation flow.

**Production code — keep as-is**

- `language` / `answer_language` defaults of `"es"` in `app/assistant/care_contracts.py:128, 129, 142`, `app/assistant/graph.py` (many lines), `app/assistant/tools.py:327`. Per user choice, the ISO code `"es"` stays; only the surrounding prose is translated.
- `INJECTION_PATTERNS` (English entries) stay.
- The Spanish attribution-stripping regex at `graph.py:3130` stays as a defensive fallback.
- All Latin scientific plant names in test fixtures stay.
- Plant common names (`"Pata de oso"`, `"Helecho"`, `"Pata"`, `"Monstera"`) stay as-is in test fixtures — they are locale-specific botanical references, not code prose.

**Production code — translate remaining user-facing data fields (follow-up to verification warnings)**

- `backend/app/identification/repository.py:13-18` — translate `_possible_match_copy` to English. New copy: `"Possible match, not definitive. Confidence {confidence}; confirm after reviewing visible traits and GBIF taxonomy."`. Old Spanish rows in `identification_candidates.possible_match_copy` stay as-is (no data migration); new rows are written in English.
- `backend/app/profile_garden/repository.py:22-30` — translate `SECTION_TOPICS` keys to English. New map: `{"description": "description", "characteristics": "characteristics", "conditions": "conditions", "care": "care", "pests": "pests", "diseases": "diseases", "recommendations": "recommendations"}`. **This is a breaking API change for any client reading `PlantProfileResponse.sections` JSON keys (`"descripcion"`, `"caracteristicas"`, etc.).** Frontend consumers must update to the new English keys. Old Spanish section rows in `plant_profiles.sections` stay as-is until the profile is regenerated.
- `backend/app/profile_garden/repository.py:222` — translate the section fallback to `f"Insufficient evidence for {fallback} of {scientific_name}."`.
- `backend/app/profile_garden/repository.py:228-229` — translate the RAG-limitation to `"Profile generated with limited RAG evidence; avoid critical care decisions without reviewing additional sources."`.
- `backend/app/profile_garden/repository.py:233` — translate the partial-confidence message to `"Partial confidence: the recommendations are presented as orientative, not categorical."`.
- `backend/app/assistant/repository.py:101` — translate the internal `ValueError` to `"The selected plant does not exist in your garden."`.
- `backend/app/providers/mocks.py:71` — translate the mock vision `visible_traits` to `["fleshy leaves", "compact growth"]`.

**Test code — translate incidental Spanish; keep language-behavior tests in Spanish (extended)**

- `backend/tests/test_assistant_agent.py` — translate all Spanish `user_message` fixtures, Spanish `model_response` fixtures, Spanish `FakeTools` stub outputs, and Spanish assertion substrings to English, **except** in the following language-behavior tests that exist to verify a language-handling guarantee (these stay in their original language because that is the test point):
  - `test_classifier_prompt_uses_actual_message_language_and_ignores_switch_requests` (line 626) — Spanish/English mixed message; keeps the language-switch-attack test point.
  - `test_spanish_message_requesting_english_uses_classifier_spanish_for_fallback` (line 666) — keeps the language-switch-attack regression test.
  - `test_minimal_fallback_routes_injection_as_unsafe` (line 1630) — keeps the Spanish prompt-injection message; `INJECTION_PATTERNS` English entry covers English injection. (Once the deterministic-classifier Spanish-keyword paths are removed, this test will route to the LLM classifier and the assertion still holds.)
  - `test_minimal_fallback_routes_*` family (lines 1647-1759) — exercise the deterministic-classifier Spanish-keyword paths that are being deleted; rewrite these tests to use the LLM-classifier path, or fold them into the existing `test_classifier_*` LLM-classifier tests.
  - `test_safety_boundary_cases` parametrize (line 6618) — keeps the 3 Spanish safety-sensitive messages (the Spanish is the test point — verifying that the safety classifier routes regardless of user language).
  - `test_multilingual_pest_question_routes_by_schema_state_not_keywords` (line 6428) — keeps the Italian model_response and Italian user message; this is a multilingual regression test.
  - `test_non_english_evidence_reaches_model_without_keyword_matching` (line 5782) — the title says `"Guia de riego en italiano"` and the snippet is Italian; keep the Italian content (it is the test point). The Spanish word `"italiano"` in the title can be replaced with `"Italian"` when translating.
  - `test_non_english_snippet_reaches_judge_without_keyword_filter` (line 5620) — keeps the Spanish `title="Guia de seguridad para mascotas"` and Spanish snippet `"Planta toxica para gatos y perros. Mantener fuera del alcance."` (or translate to any non-English language and update the assertion accordingly). This test exists specifically to verify that non-default-language snippets reach the judge.
  - The disclaimed-guidance / RAG / URL-stripping test families (`test_general_guidance_prompt_requires_separation_and_safety_prohibitions` line 6094, `test_pest_question_with_relevant_context_routes_to_disclaimed_guidance` line 6210, `test_disclaimed_guidance_*` line 6245, `test_disclaimed_guidance_emits_no_ingestion_claims` line 6293, `test_partial_evidence_ingestion_uses_only_validated_source_support` line 6323, `test_safety_sensitive_missing_aspect_keeps_conservative_fallback` line 6404, `test_combined_rag_web_insufficient_routes_to_disclaimed_guidance` line 6481, `test_pesticide_instruction_request_does_not_return_chemical_advice` line 6699, `test_grounded_prompt_prohibits_urls_and_source_labels` line 6751, `test_grounded_prompt_structured_api_no_attribution_instruction` line 6827, `test_grounded_response_*` line 6867-7027) — translate the Spanish `model_response` fixtures to English, and update the assertion substrings to match the new English production prompt.
  - `test_no_deterministic_emergency_prose_on_total_generation_failure` (line 5663) and `test_rag_fallback_does_not_return_prewritten_prose` (line 5680) — keep these assertions as regression tests for prewritten prose, but translate the forbidden Spanish phrases to their English equivalents (`"I could not generate"`, `"Try again"`, `"A practical guide is:"`, `"For"` not `"Para"`).
  - `test_assistant_reports_degraded_knowledge_limitations` (line 2022) — translate the assertion substrings to English (the `FakeTools` stub at line 471 will also be translated).
  - `test_conservative_safety_fallback_for_pet_safety_without_direct_evidence` (line 3206) and `test_conservative_safety_fallback_for_edibility_without_direct_evidence` (line 3225) — translate the assertion substrings to English (the production `_conservative_safety_answer` template is translated).
  - Default `FakeTools` fixtures in `test_assistant_agent.py` (lines 213, 218, 385, 463, 465, 467, 469, 471, 473, 475, 477, 478, 479, 481, 483) — translate `model_response="Respuesta sintetizada por modelo."` → `"Synthesized model response."`, `model_response="Respuesta de fallback renderizada por modelo."` → `"Model-rendered fallback response."`, `knowledge_content="Requiere riego moderado y sustrato con buen drenaje."` → `"Requires moderate watering and well-draining substrate."`, `metadata={"title": "Ficha botanica"}` → `{"title": "Botanical record"}`, and all the `FakeTools.generate_text` Spanish stub outputs at lines 463-481. This is a sweeping change because the default `model_response` is asserted in ~100 test bodies.
  - New test functions for display-name preservation (lines 7057, 7081, 7105, 7142, 7168, 7196, 7216, 7236, 7256, 7276, 7297) — translate the Spanish assertion substrings (`"Cuando te dirijas a la planta en la respuesta"`, `"usa siempre el nombre proporcionado como 'Planta seleccionada'"`, `"Nunca reemplaces ese nombre por el nombre comun"`, `"el nombre cientifico"`, `"el binomio"`) to English, and translate the Spanish `model_response` fixtures (lines 7199, 7201, 7222, 7242, 7259, 7261).
  - Spanish `classifier_data` dicts with `"language": "es"`, `"answer_language": "es"` — there are ~40 of these in the test file. For tests whose purpose is to verify routing/intent/aspect logic (not language behavior), translate to `"language": "en"`, `"answer_language": "en"` and translate the corresponding user messages to English. Keep Spanish only in language-behavior tests.
- `backend/tests/test_reminders.py` — translate the Spanish `notes` / `location` / `action` values to English (they are incidental Spanish test data), but keep the Spanish plant common names (`"Helecho"`, `"Pata de oso"`) per the user choice.

**What is not changing**

- Frontend, mobile, docs (no Spanish in `backend/`, and this change is scoped to `backend/`).
- `pyproject.toml`, `alembic.ini`, `Dockerfile`, `.env.example`, `scripts/*.py`, `migrations/versions/*.py` (all already English).
- The ISO 639-1 literal string `"es"` in defaults, Pydantic models, and the Pydantic validator's empty-input fallback.
- The English `INJECTION_PATTERNS` entries.
- The English `According to …` attribution regex in `graph.py:3129`.
- Any Latin scientific plant name in code or tests.
- Locale-specific plant common names in test fixtures.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities (extended)

- `assistant-agent` — the **Multilingual care intent classification** and related requirements change: Spanish-keyword-based deterministic intent detection is removed (including `_is_light_measurement_request`, `_is_edibility_question`, `_is_pet_safety_question`, `_message_has_plant_context`, `_extract_recurrence`, `_extract_reminder_action`, `_wants_reminder_suggestion`); the LLM classifier and explicit request fields become the sole semantic-intent path. The **Conservative safety fallback** requirement changes wording so the fallback template is English. The **Grounded answer prompt** and **Disclaimed guidance prompt** requirements change wording to English, **including the new display-name preservation paragraphs (lines 3002-3004, 3065-3067) and the new connector-priority paragraphs (lines 3051-3054, 3082-3083)**. The **Prompt-injection resistance** requirement changes the matched-pattern language to English (the Spanish pattern entries are removed; English ones stay).
- `plant-profile-garden` — the **Confirmation / deletion** requirement changes the user-facing error message wording to English. A new **Plant profile sections and limitations are English** requirement is added asserting that `PlantProfileResponse.sections` keys and `PlantProfileResponse.limitations` values are written in English.
- `plant-identification-taxonomy` — the **Image upload validation** and **Vision analysis failure** requirements change user-facing error messages to English. The **MaaS visual candidates** requirement gains a new scenario asserting that `TaxonomyCandidate.possible_match_copy` is in English.
- `reminders` — the **Reminder lifecycle error handling** requirement changes the user-facing error messages to English.
- `light-meter` — the **Light measurement error handling** requirement changes the user-facing error message to English.
- `authentication-home` — the **Password recovery** requirement changes the recovery response message to English.
- `project-foundation` — the **Home navigation labels** requirement changes the 6 home-screen labels to English.

## Impact

- **API surface change (additive but observable):** every Spanish `HTTPException.detail` and every `RecoveryResponse.message` becomes English. The Spanish-to-English content change is observable to any client that displays raw error/detail strings. Existing `HomeAccessItem.label` consumers in the frontend will need to update any hardcoded Spanish fallbacks.
- **Test impact (larger than initially estimated):** ~100 test messages, 30 assertion substrings, the `FakeTools.__init__` defaults (`model_response`, `knowledge_content`, `metadata.title`), the `FakeTools.generate_text` Spanish stubs (8 stub outputs at lines 463-481), and 40 `classifier_data` dicts with `"language": "es"` are translated. The 5-6 language-behavior tests stay in their original language. Several `test_minimal_fallback_*` tests are removed (the deterministic-classifier Spanish-keyword paths they exercise are gone) and folded into the LLM-classifier test families. The 11 new display-name / nickname test functions (lines 7057-7346) require updating their Spanish assertion substrings and Spanish `model_response` / `knowledge_content` fixtures.
- **Deterministic-classifier impact:** `_deterministic_classification` is reduced to a non-semantic conservative-fallback router (only the `unsafe_or_injection` branch and an empty `plant_care_question` / `general` passthrough). Anything that used to be deterministically routed via Spanish keywords now requires the LLM classifier to succeed; this is the intended behavior per `openspec/config.yaml` and is the project's standing design.
- **No data migration needed:** the `suggestion_justification` field in the DB is stored as user-facing prose; new English values will be written, old Spanish values remain readable as-is.
- **No provider / model / schema change:** the Pydantic model `CareClassification` keeps the same shape; only the default value and validator message wording change.
