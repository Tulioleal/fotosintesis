## Context

The `backend/` codebase currently contains three categories of Spanish residue that the proposal aims to remove:

1. **User-facing strings** — `HomeAccessItem.label` values, `HTTPException.detail` messages, and the `RecoveryResponse.message` reply are written in Spanish. These flow directly to clients.
2. **Assistant prompts and safety templates** — `_grounded_answer_prompt`, `_general_guidance_with_disclaimer_prompt`, `_conservative_safety_answer` templates, `_taxonomy_context` strings, `_simple_fallback_draft` defaults, and the enriched-facts labels in `_model_generation_failed_draft` are Spanish. The Spanish attribution-stripping regex is the only piece kept as a defensive fallback.
3. **Spanish semantic-intent keyword detection** — `_deterministic_classification` in `app/assistant/graph.py` (and the helper functions `_is_light_measurement_request`, `_message_has_plant_context`, `_is_edibility_question`, `_is_pet_safety_question`, `_extract_recurrence`, `_extract_reminder_action`, `_wants_reminder_suggestion`) routes intents like reminder creation, light measurement, plant identification, edibility, pet safety, native range, and taxonomy using translated word lists, regexes, and English/Spanish-only heuristics.

The repo's `openspec/config.yaml` explicitly forbids this last category for semantic plant-care behavior and reserves deterministic code for non-semantic safety boundaries, schema validation, enum validation, provider selection, trusted URL/domain checks, non-empty text checks, and conservative fallback routing after model failure. The project's standing rule is that the codebase should be English unless another language is explicitly needed for testing.

## Goals / Non-Goals

**Goals:**

- Translate every Spanish user-facing string in `backend/app/api/*.py` to English, preserving the meaning of the validation/error message.
- Translate the Spanish assistant prompts, safety templates, taxonomy context, and fallback draft defaults in `app/assistant/graph.py` to English. The model is now instructed to write in English.
- Translate the Spanish `INJECTION_PATTERNS` entries to English; keep English entries and keep the non-semantic injection check itself.
- Remove the Spanish-keyword semantic-intent detection paths inside `_deterministic_classification` and the helper functions that perform Spanish keyword matching. The LLM classifier and the explicit request fields become the sole semantic-intent path.
- Reduce `_deterministic_classification` to a non-semantic conservative-fallback router that retains only the `unsafe_or_injection` branch and an empty/passthrough behavior (e.g. `plant_care_question_unknown` with `topic: "general_care"`).
- Translate incidental Spanish in `backend/tests/test_assistant_agent.py` and `backend/tests/test_reminders.py` to English, except for the 5 language-behavior regression tests that exist to verify language handling.
- Fold the deleted `test_minimal_fallback_routes_*` tests into the LLM-classifier test families.

**Non-Goals:**

- No frontend, mobile, or docs change. The change is scoped to `backend/`.
- No migration of the `suggestion_justification` field in the database. Old Spanish values remain readable as-is; new values will be English.
- No Pydantic model shape change. `CareClassification` keeps the same fields; only the default value and validator message wording change.
- No provider, model, or schema change.
- The ISO 639-1 literal string `"es"` in `language` / `answer_language` defaults stays. The "es" default applies to user-facing answer language, not the language of the surrounding prose.
- The Spanish attribution-stripping regex (`graph.py:3130`) stays as a defensive fallback.
- The English `INJECTION_PATTERNS` entries stay.
- Latin scientific plant names in code and tests stay.
- Locale-specific plant common names in test fixtures stay (they are botanical references, not code prose).

## Decisions

### Decision 1: LLM classifier is the sole semantic-intent path

The Spanish-keyword semantic-intent detection in `_deterministic_classification` and its helper functions is removed. The multilingual LLM classifier and the explicit request fields (`plant`, `plant_binomial_name`, `plant_scientific_name`, `reminder_action`, `light_measurement`) are the sole semantic-intent path.

The deterministic fallback retains only the non-semantic `unsafe_or_injection` branch and a passthrough for `plant_care_question_unknown` / `general_care`. The fallback MAY NOT route `reminder_request`, `light_measurement_question`, or `plant_identification_question` based on Spanish keyword patterns.

**Alternatives considered:**

- Keep the Spanish keyword paths as a "belt and suspenders" fallback in addition to the LLM classifier. Rejected: this is exactly the behavior `openspec/config.yaml` forbids. It also creates two competing semantic-intent paths whose outputs can disagree.
- Replace the Spanish keyword paths with English keyword paths. Rejected: any translated word list is the same anti-pattern under a different language.
- Move the semantic-intent detection into a smaller dedicated LLM call. Rejected: the existing classifier contract (`language`, `answer_language`, `intent`, `topic`, `required_aspects`, `plant_reference`, `confidence`, `needs_retrieval`) is already complete and validated. Adding another LLM hop adds latency and a new failure mode without adding capability.

### Decision 2: `_deterministic_classification` becomes a non-semantic conservative-fallback router

After removing the Spanish-keyword paths, `_deterministic_classification` only retains:

- The non-semantic `unsafe_or_injection` branch (relying on `INJECTION_PATTERNS`).
- A passthrough that returns `None` for plant-care messages with no LLM-classifier output, so the caller falls through to the LLM classifier or asks for clarification.

The function no longer returns a populated `CareClassification` for any non-unsafe Spanish-keyword path.

**Alternatives considered:**

- Inline the `unsafe_or_injection` check at the call site. Rejected: keeping the function preserves the existing call surface and makes the conservative-fallback boundary explicit.
- Delete the function entirely. Rejected: the `unsafe_or_injection` branch is a non-semantic safety boundary, which is allowed by `openspec/config.yaml`, and the function is the natural home for it.

### Decision 3: Helper functions are deleted, not refactored

`_is_light_measurement_request`, `_message_has_plant_context`, `_is_edibility_question`, `_is_pet_safety_question`, `_extract_recurrence`, `_extract_reminder_action`, and `_wants_reminder_suggestion` are deleted. Plant context is already captured by the explicit `plant` / `plant_binomial_name` / `plant_scientific_name` request fields. Reminder action and recurrence are captured by the explicit reminder request fields and the user-confirmation flow. Edibility, pet safety, and light-measurement intents are produced by the LLM classifier.

**Alternatives considered:**

- Convert them into English keyword checks. Rejected: same anti-pattern.
- Keep them as English helpers behind a feature flag. Rejected: dead code with a different name is still dead code.
- Move them to the LLM classifier as additional classifier aspects. Rejected: `topic` and `required_aspects` already cover these semantic axes.

### Decision 4: Prompts and templates are translated to English (extended)

`_grounded_answer_prompt`, `_general_guidance_with_disclaimer_prompt`, `_conservative_safety_answer` templates, `_taxonomy_context` strings, `_simple_fallback_draft` defaults, the enriched-facts labels in `_model_generation_failed_draft` (`"Contradiccion detectada"`, `"Limitacion"`, `"Aspecto faltante"`), and the connector phrases (`"Como pauta general…"` → `"As a general guideline…"`, `"En terminos generales…"` → `"In general terms…"`, `"Una practica habitual complementaria…"` → `"A common complementary practice is…"`, `"Como referencia complementaria…"` → `"As a complementary reference…"`) are translated to English. The model is now instructed to write in English.

The new **display-name preservation paragraphs** at `graph.py:3002-3004` and `graph.py:3065-3067` and the new **connector-priority paragraphs** at `graph.py:3051-3054` and `graph.py:3082-3083` are part of the system-prompt translation: the prose is translated, and the language-neutral English placeholder for `plant_name` is preserved (this is owned by the sibling `use-nickname-in-user-facing-prose` change — the placeholder itself stays English, so the translation here only changes the surrounding prose).

**Alternatives considered:**

- Keep the prompts in Spanish and have the model translate to the answer language. Rejected: this is slower, error-prone, and the user's rule is that the codebase should be English unless another language is explicitly needed for testing.
- Use the LLM to generate the prompts dynamically. Rejected: prompts are deterministic and reviewed; dynamic generation loses the deterministic review boundary.

### Decision 5: The Spanish attribution-stripping regex is kept as a defensive fallback

`graph.py:3130` (the Spanish attribution-stripping regex) stays. The English regex on the line above is the primary one; the Spanish regex is a defensive fallback in case a model output accidentally includes Spanish attribution patterns (e.g. from prior training data, prompt injection, or downstream LLM fallbacks). The model is now instructed to write in English, so this should not fire in normal operation.

**Alternatives considered:**

- Delete the Spanish regex entirely. Rejected: defensive code is cheap; a single line of regex protects against a class of failure that would otherwise leak attribution noise into user-facing prose.
- Replace it with a more aggressive catch-all regex. Rejected: overly aggressive regex tends to strip legitimate content; a narrowly-scoped Spanish-pattern fallback is the right scope.

### Decision 6: Spanish `INJECTION_PATTERNS` entries are translated to English

The Spanish entries in `INJECTION_PATTERNS` (`"ignora las instrucciones"` → `"ignore the instructions"`, `"omite las reglas"` → `"omit the rules"`) are translated to English. The injection-pattern list itself is a non-semantic safety boundary, so this is allowed by `openspec/config.yaml`. The English entries that already exist stay.

**Alternatives considered:**

- Add the Spanish entries to a new list of multilingual injection patterns. Rejected: deterministic multilingual pattern lists are the same anti-pattern at a different layer. The LLM classifier handles non-English injection detection.
- Keep the Spanish entries alongside the English ones. Rejected: the user's standing rule is English unless another language is explicitly needed for testing, and the LLM classifier is the multilingual detection path.

### Decision 7: User-facing strings are translated, ISO code `"es"` stays

The 6 `HomeAccessItem.label` values, 23 `HTTPException.detail` strings, and the `RecoveryResponse.message` are translated to English. The ISO 639-1 literal string `"es"` in `language` / `answer_language` defaults stays. The `"es"` default is the user's `answer_language`, not the language of the surrounding prose; it is correctly understood as a code, not a sentence.

**Alternatives considered:**

- Change the default `language` to `"en"`. Rejected: the user explicitly chose to keep the `"es"` default. The default applies to the user-facing answer language, not the language of the surrounding prose.

### Decision 8: Language-behavior tests stay in their original language (extended)

The 5-6 language-behavior tests in `test_assistant_agent.py` keep their original language where that language is the test point. The `test_minimal_fallback_routes_*` family (lines 1647-1759) is rewritten to use the LLM-classifier path or folded into the existing `test_classifier_*` tests, because the deterministic-classifier Spanish-keyword paths they exercise are gone.

- `test_classifier_prompt_uses_actual_message_language_and_ignores_switch_requests` (line 626) — Spanish/English mixed message; keeps the language-switch-attack test point.
- `test_spanish_message_requesting_english_uses_classifier_spanish_for_fallback` (line 666) — keeps the language-switch-attack regression test.
- `test_minimal_fallback_routes_injection_as_unsafe` (line 1630) — keeps the Spanish prompt-injection message; once the deterministic-classifier Spanish-keyword paths are removed, this test routes to the LLM classifier and the assertion still holds.
- `test_safety_boundary_cases` parametrize (line 6618) — keeps the 3 Spanish safety-sensitive messages (the Spanish is the test point — verifying that the safety classifier routes regardless of user language).
- `test_multilingual_pest_question_routes_by_schema_state_not_keywords` (line 6428) — keeps the Italian model_response and Italian user message; this is a multilingual regression test.
- `test_non_english_evidence_reaches_model_without_keyword_matching` (line 5782) — the title says `"Guia de riego en italiano"` and the snippet is Italian; keep the Italian content (it is the test point). The Spanish word `"italiano"` in the title can be replaced with `"Italian"` when translating.
- `test_non_english_snippet_reaches_judge_without_keyword_filter` (line 5620) — keeps the Spanish `title="Guia de seguridad para mascotas"` and Spanish snippet `"Planta toxica para gatos y perros. Mantener fuera del alcance."` (or translate to any non-English language and update the assertion accordingly). This test exists specifically to verify that non-default-language snippets reach the judge.

**Alternatives considered:**

- Translate all 5-6 language-behavior tests to English and rely on the LLM-classifier tests to cover the language-switch regression. Rejected: the 5-6 tests are the only direct regression coverage for the language-switch guarantee and the multilingual routing guarantee. Translating them away from Spanish/Italian removes that coverage.

### Decision 9: `test_reminders.py` Spanish fixture values are translated, plant common names stay

The Spanish `notes` / `location` / `action` values in `test_reminders.py` are translated to English (they are incidental test data). The Spanish plant common names (`"Helecho"`, `"Pata de oso"`) stay because they are locale-specific botanical references, not code prose.

**Alternatives considered:**

- Translate the plant common names to English (`"Fern"`, `"Bear's Paw"`). Rejected: the user explicitly chose to keep locale-specific plant common names as-is.

### Decision 10: Forbidden Spanish fallback phrases in tests are replaced with English equivalents

`test_no_deterministic_emergency_prose_on_total_generation_failure` (line 5663) and `test_rag_fallback_does_not_return_prewritten_prose` (line 5680) assert that the answer does NOT contain specific fallback phrases. After the production change translates the fallback prose to English, the forbidden phrases are updated to their English equivalents (`"I could not generate"`, `"Try again"`, `"A practical guide is:"`, `"For"` not `"Para"`).

**Alternatives considered:**

- Leave the forbidden phrases as Spanish and let the test fail. Rejected: the production change translates the fallback prose to English, so the test must forbid the new English phrases.

### Decision 11: Default `FakeTools` fixtures and `classifier_data` dicts are translated (extended)

The default `FakeTools` fixtures in `test_assistant_agent.py` (lines 213, 218, 385, 463, 465, 467, 469, 471, 473, 475, 477, 478, 479, 481, 483) and the Spanish `classifier_data` dicts with `"language": "es"`, `"answer_language": "es"` (~40 of them) are translated to English. This is a sweeping change because the default `FakeTools.model_response` is asserted in ~100 test bodies.

For the `classifier_data` dicts, the translation rule is:

- Tests whose purpose is to verify routing/intent/aspect logic (not language behavior) translate to `"language": "en"`, `"answer_language": "en"` and translate the corresponding user messages to English.
- Tests whose purpose is to verify language behavior (the 5-6 language-behavior tests) keep Spanish/Italian.

The 11 new display-name / nickname test functions at lines 7057, 7081, 7105, 7142, 7168, 7196, 7216, 7236, 7256, 7276, 7297 translate their Spanish assertion substrings and Spanish `model_response` / `knowledge_content` fixtures to English, while preserving the test point (that the nickname round-trips through the model response). The sibling `use-nickname-in-user-facing-prose` change owns the nickname-in-prose requirement; this change owns the English translation of the test bodies.

**Alternatives considered:**

- Keep the `FakeTools` defaults Spanish and only translate the test bodies that use them. Rejected: the default `model_response` is asserted in ~100 test bodies, and a Spanish default would create a hidden Spanish residue in the test suite. The sweeping translation is cleaner and matches the user's "codebase should be English" rule.
- Translate the 5-6 language-behavior tests' `classifier_data` dicts to English. Rejected: those tests exist specifically to verify language behavior; translating the `classifier_data` would defeat the test point.

## Risks / Trade-offs

- [Risk] Removing the Spanish-keyword semantic-intent detection means the LLM classifier is the only path that detects `reminder_request`, `light_measurement_question`, `plant_identification_question`, `edibility`, `pet_safety`, and `native_range` intents. → Mitigation: The LLM classifier contract is already complete and validated. The existing `test_classifier_*` tests cover each intent. The assistant asks the user to confirm before creating a reminder, so the regression risk is bounded by the existing confirmation flow.

- [Risk] The LLM classifier is the sole semantic-intent path, so its latency and failure rate now affect routing for more intents. → Mitigation: The deterministic fallback (only `unsafe_or_injection` + passthrough) is the existing safety net. The `Classifier fallback handling` requirement already prescribes repair retry, bounded-failure metadata, and `minimal_routing_fallback_used` diagnostics.

- [Risk] Translating user-facing error messages to English breaks frontend consumers that display raw `HTTPException.detail` strings. → Mitigation: The proposal explicitly calls this out as an additive but observable API surface change. Frontend consumers are expected to update any hardcoded Spanish fallbacks. The home labels change is captured in the project-foundation spec.

- [Risk] The Spanish attribution-stripping regex at `graph.py:3130` may never fire after the production translation, raising the question of whether it should be removed. → Mitigation: The user explicitly chose to keep it as a defensive fallback. The cost is one line of regex; the benefit is protection against a class of failure that would otherwise leak attribution noise into user-facing prose.

- [Risk] Translating the prompts and templates to English means downstream LLM outputs are now expected to be in English by default, but the `answer_language` may still be Spanish (e.g. for a Spanish user message). → Mitigation: The model is instructed in English and is told to write its answer in `answer_language`. The multilingual classifier contract already enforces `answer_language` from the actual message language, ignoring language-switch requests. Existing `test_classifier_prompt_uses_actual_message_language_and_ignores_switch_requests` covers this guarantee.

- [Risk] The 5 language-behavior tests stay in Spanish/Italian, which may confuse contributors who expect all tests to be in English. → Mitigation: Each of those tests has a comment or docstring explaining that the language is the test point. A `tests/README` or test-file docstring can call this out. The proposal explicitly enumerates which tests stay and why.

- [Risk] Removing the Spanish entries from `INJECTION_PATTERNS` means a Spanish prompt-injection message that the LLM classifier would have caught now relies entirely on the LLM classifier. → Mitigation: The LLM classifier is multilingual and is the project's stated path for semantic detection. The `unsafe_or_injection` branch is preserved. The non-semantic safety boundary is intact.

- [Risk] The default `FakeTools` fixtures are asserted in ~100 test bodies. A sweeping translation risks breaking many tests in one pass. → Mitigation: The translation is mechanical (Spanish → English with the meaning preserved). The forbidden-phrase tests in `test_no_deterministic_emergency_prose_on_total_generation_failure` and `test_rag_fallback_does_not_return_prewritten_prose` are the only tests that assert the absence of a phrase, and those are updated to forbid the new English phrases. The remaining tests assert presence or behavior, and the translation only changes the surface text. The full test suite run after the translation catches any miss.

- [Risk] Translating ~40 `classifier_data` dicts from Spanish to English may break tests that depend on the Spanish language to assert routing. → Mitigation: The translation rule is: tests whose purpose is to verify language behavior keep Spanish; tests whose purpose is to verify routing/intent/aspect logic translate to English. The 5-6 language-behavior tests are explicitly enumerated in Decision 8. All other tests are translated.

- [Risk] The new display-name preservation paragraphs and connector-priority paragraphs (`graph.py:3002-3004, 3051-3054, 3065-3067, 3082-3083`) interact with the sibling `use-nickname-in-user-facing-prose` change. → Mitigation: This change owns the English translation of the surrounding prose; the sibling change owns the language-neutral English placeholder for `plant_name` ("your plant" / "not specified"). The placeholder is preserved by both changes; the surrounding prose is translated by this change. The two changes are independent in the diff but co-dependent in the spec (the placeholder stays English; the prose is translated).

## Migration Plan

This change is a single deployable release with no data migration. The steps are:

1. **Code change** — translate the production strings, prompts, templates, and `INJECTION_PATTERNS` entries (including the new `graph.py:649` validation message, `graph.py:697-698` web-sources disclaimer, `graph.py:2323, 2327, 2331` enriched-facts labels, and the new display-name preservation and connector-priority paragraphs at `graph.py:3002-3004, 3051-3054, 3065-3067, 3082-3083`); remove the Spanish-keyword semantic-intent detection paths; reduce `_deterministic_classification` to a non-semantic conservative-fallback router.
2. **Test change** — translate incidental Spanish test fixtures and assertion substrings (including the default `FakeTools` fixtures and ~40 `classifier_data` dicts); fold the deleted `test_minimal_fallback_routes_*` tests into the LLM-classifier test families; update forbidden-phrase assertions to use the new English phrases; update the 11 new display-name / nickname test functions to use English assertion substrings and English `model_response` / `knowledge_content` fixtures; keep the 5-6 language-behavior tests in their original language.
3. **Run the full test suite** — `pytest backend/tests/`. All translated tests must pass; the 5-6 language-behavior tests must still pass with their original Spanish/Italian messages.
4. **Manual smoke** — exercise the home screen, profile garden, identifications, reminders, light meter, auth recovery, and assistant in the running stack to confirm the English labels and error messages render correctly.
5. **Rollback** — revert the single commit. There is no data migration and no schema change, so a rollback is a clean revert.

## Open Questions

- Should the project-foundation capability also be updated to record that the home navigation labels are in English, in addition to authentication-home? — Decided: yes, the project-foundation delta spec adds an `ADDED Requirement: Home navigation labels are English` to capture the cross-cutting concern. The user listed project-foundation in the proposal.
- Should the `test_minimal_fallback_routes_*` family be folded into the LLM-classifier tests or rewritten to use the LLM-classifier path explicitly? — Decided: rewrite to use the LLM-classifier path explicitly, with a comment noting that the deterministic-classifier Spanish-keyword path is gone. This preserves the test intent and gives the LLM-classifier path direct coverage.
- Should the Spanish attribution-stripping regex at `graph.py:3130` be removed in a follow-up change once production confirms it never fires? — Decided: keep for now. The cost is one line; the benefit is defensive coverage. Revisit in a future change if desired.
