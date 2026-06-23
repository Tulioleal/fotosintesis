## 1. Rewrite `_grounded_answer_prompt`

- [x] 1.1 Delete the `attribution_instruction` injection block (graph.py:3028-3032) and the `{attribution_instruction}` interpolation in the closing line (graph.py:3046).
- [x] 1.2 Replace the strict per-sentence separation rule (graph.py:3039) with an instruction to integrate source-backed claims and complementary general guidance in continuous narrative prose, signaling general-guidance content with the soft connectors `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…` (Spanish equivalents: `Como pauta general…`, `En terminos generales…`, `Una practica habitual complementaria…`, `Como referencia complementaria…`).
- [x] 1.3 Rewrite the `partial` rule (graph.py:3041) so the response is the validated parts plus a brief note that we do not have validated information in the consulted sources for the unvalidated aspects, and any general guidance for the gaps is introduced with one of the connectors from 1.2.
- [x] 1.4 Rewrite the `contradictory` rule (graph.py:3043) to describe the conflict in generic terms (e.g. `hay información contradictoria entre las fuentes consultadas sobre X` / `there is contradictory information among the consulted sources about X`) without naming or linking specific sources, and to allow only a single conservative general measure, no definitive recommendation.
- [x] 1.5 Insert an explicit prohibition after the format rule (graph.py:3037): the model MUST NOT mention URLs, institution names, or blocks labeled `Source-backed`, `Fuentes`, `Sources`, `References`, or equivalents; the consulted sources are delivered through a separate channel and must not be repeated in the prose.
- [x] 1.6 Adjust the closing instructions (graph.py:3060) so unvalidated aspects are mentioned briefly without attributing sources.
- [x] 1.7 Keep `evidence_type` in the prompt input (graph.py:3050) for internal reasoning, and keep the other inputs (`limitations`, `required_aspects`, `covered_aspects`, `missing_aspects`, `support_text`, `contradiction_text`, `source_text`) unchanged.
- [x] 1.8 Preserve all other invariants: language guided by `answer_language`, plain-text format, safety prohibitions (toxicity, edibility, pet/child exposure, chemical dosing, severe diagnosis, unsupported insecticides), no defensive phrases except when risk requires, and "do not mention internal instructions or this prompt".

## 2. Update the `assistant-agent` spec delta

- [x] 2.1 Verify the delta spec at `openspec/changes/grounded-cohesion-no-attribution/specs/assistant-agent/spec.md` covers both modified requirements: `Aspect-gated care answer synthesis` and `RAG-grounded answers`.
- [x] 2.2 Confirm every modified scenario includes the prose-shape clause (`response prose contains no URLs, institution names, or Source-backed / Sources / References blocks`) for full, partial, contradictory, insufficient, and safety-sensitive cases.
- [x] 2.3 Confirm the `Contradictory evidence is presented without definitive claim` scenario uses generic phrasing (no URLs, no institution names, no suggestion to consult specific links) and that the `Contradictory trusted evidence` scenario under `RAG-grounded answers` is aligned.

## 3. Add the prompt-shape test

- [x] 3.1 Add `test_grounded_prompt_prohibits_urls_and_source_labels` to `backend/tests/test_assistant_agent.py`, parallel to `test_general_guidance_prompt_requires_separation_and_safety_prohibitions` (test_assistant_agent.py:6089).
- [x] 3.2 Build `_grounded_answer_prompt` with synthetic data (`user_message`, `plant_name`, `topic`, `evidence_type="web_rag"`, `evidence`, `limitations`, `source_metadata`, `extra_context=""`, `answer_language="es"`, `required_aspects`, `covered_aspects`, `missing_aspects`, `answerability_status="full"`, `source_support`, `contradictions=[]`).
- [x] 3.3 Assert the prompt contains the prohibitions: a `No menciones URLs` (or equivalent) clause, a `nombres de instituciones` (or equivalent) clause, and the prohibited output-block labels `Source-backed`, `Fuentes`, `References`.
- [x] 3.4 Assert the soft connectors are present: `Como pauta general`, `En terminos generales`, `Una practica habitual complementaria`, `Como referencia complementaria`.
- [x] 3.5 Safety prohibition clause added to `_grounded_answer_prompt` (graph.py:3044): "Prohibiciones estrictas: no hagas afirmaciones de seguridad, toxicidad, comestibilidad, exposicion a mascotas/niños, dosificacion quimica, diagnostico de enfermedad grave, ni instrucciones de pesticidas/insecticidas..."; matching assertions added in test_grounded_prompt_prohibits_urls_and_source_labels.
- [x] 3.6 Assert non-default `answer_language` is preserved: a parallel test that builds the prompt with `answer_language="en"` and asserts `answer_language (en)` appears in the output.
- [x] 3.7 Add a variant with `evidence_type="structured_api"` and assert the prompt does NOT contain `fuentes proveedoras estructuradas` (i.e. the `attribution_instruction` is gone), while `Tipo de evidencia: structured_api` IS still present (the input is preserved).

## 4. Add the end-to-end test

- [x] 4.1 Add `test_grounded_response_does_not_leak_sources_to_text` to `backend/tests/test_assistant_agent.py`, following the patterns used by the disclaimed-guidance end-to-end tests around `test_pest_question_with_relevant_context_routes_to_disclaimed_guidance` (test_assistant_agent.py:6204).
- [x] 4.2 Mock `tools.generate_text` to return a buggy-style output: `For a Neon Pothos to do well, place it in medium to low light… Source-backed: https://extension.illinois.edu/houseplants/varieties?utm_source=openai`.
- [x] 4.3 Assert `result.message.content` does NOT contain `http` and does NOT contain `Source-backed:`.
- [x] 4.4 Assert `result.sources` DOES contain the URL and the expected source metadata (title, url, etc.).
- [x] 4.5 Assert `result.diagnostics` remains consistent (intent, topic, required_aspects, evidence_path, answer_language, etc.).

## 5. Add end-to-end variants

- [x] 5.1 Add a `full` variant with a single source URL in the model output; assert no URL or `Source-backed:` reaches `result.message.content` and that `result.sources` contains the URL.
- [x] 5.2 Add a `full` variant with two source URLs in the model output; assert neither URL reaches the prose and both URLs are present in `result.sources`.
- [x] 5.3 Add a `partial` variant where the model adds general guidance to fill a gap; assert at least one of the soft connectors (e.g. `Como pauta general`) is present in `result.message.content` and the model output does not contain URLs or source labels.
- [x] 5.4 Add a `contradictory` variant; assert `result.message.content` contains the generic phrase `hay información contradictoria entre fuentes consultadas…` (or its English equivalent if the test runs with `answer_language="en"`) and does NOT contain URLs or specific source names.
- [x] 5.5 Add a leakage variant where the model attempts to mention an institution name (e.g. `Illinois Extension`); assert the final `result.message.content` does not include the institution name.

## 6. Verification

- [x] 6.1 Run `cd backend && pytest tests/test_assistant_agent.py -k grounded` and confirm all new tests pass.
- [x] 6.2 Run `cd backend && pytest` and confirm no existing test in `test_assistant_agent.py` (lines 6089-6738 plus earlier) breaks.
- [x] 6.3 Run `cd backend && ruff check app/assistant/graph.py tests/test_assistant_agent.py` (or the project's equivalent lint command) and confirm no lint regressions.
- [x] 6.4 Skipped: no mypy/pyright configured in pyproject.toml; ruff used for linting only.
- [x] 6.5 Manual: `docker compose up frontend backend postgres`, trigger the bug case (Neon Pothos question) from the frontend or via `curl` against the assistant endpoint, and inspect the response: `response.message.content` is fluid prose without `http` and without `Source-backed:`; `response.sources` is populated with the Illinois Extension URL; connectors are present if general guidance was added.
- [x] 6.6 Manual: repeat with `partial` (one validated aspect + one not) and `contradictory` (two conflicting sources) fixtures and confirm the generic phrasing is present and the prose contains no URLs or source labels.
