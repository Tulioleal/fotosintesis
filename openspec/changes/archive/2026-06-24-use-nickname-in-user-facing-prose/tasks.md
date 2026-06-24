## 1. Add the nickname-in-prose instruction to all user-facing prompts

- [x] 1.1 Add the instruction paragraph to `_grounded_answer_prompt` in
  `backend/app/assistant/graph.py` (around line 3029, after the
  source-attribution prohibition paragraph and before the
  `f"Pregunta del usuario..."` block). The paragraph must tell the
  model to use the value supplied as the selected plant (the
  nickname / display name) when referring to the plant in the
  response, and to never replace it with the common name, the
  scientific name, or the binomial from the evidence, taxonomy
  context, or source metadata.
- [x] 1.2 Add the instruction paragraph to
  `_general_guidance_with_disclaimer_prompt` in
  `backend/app/assistant/graph.py` (around line 2939, after the
  four-section structure paragraph and before the prohibitions).
  The paragraph must apply to all four user-facing sections.
- [x] 1.3 Add the instruction as a `required_point` in the
  conservative safety fallback template (`_conservative_safety_draft`
  in `backend/app/assistant/graph.py` around line 2215) for all
  three variants (pet safety, edibility, generic).
- [x] 1.4 Add the instruction as a default `required_point` in
  `_simple_fallback_draft` in `backend/app/assistant/graph.py`
  (around line 2179) when the caller does not pass explicit
  `required_points`.
- [x] 1.5 Add the instruction as a default `required_point` in
  `_recovery_draft_for_answer_generation` in
  `backend/app/assistant/graph.py` (around line 2341) so recovered
  answers also honor the nickname.

## 2. Verify the investigation path still uses the operational name

- [x] 2.1 Re-read `_operational_name_for_tools` in
  `backend/app/assistant/graph.py` (around line 2765) and confirm
  it continues to derive the operational name from
  `state.plant_binomial_name` -> `_binomial_from_scientific_name`
  -> `state.plant_scientific_name`, never from
  `state.plant_hint` or `state.display_plant_name`.
- [x] 2.2 Re-read `display_plant_name` and `_display_name_for_answer`
  in `backend/app/assistant/graph.py` and confirm the priority
  remains `request.plant -> request.plant_scientific_name ->
  request.plant_binomial_name`, then the saved-plant's nickname.
  No priority change.

## 3. Add prompt-builder unit tests pinning the instruction in place

- [x] 3.1 In `backend/tests/test_assistant_agent.py`, add a unit
  test for `_grounded_answer_prompt` asserting the new instruction
  string is present.
- [x] 3.2 In `backend/tests/test_assistant_agent.py`, add a unit
  test for `_general_guidance_with_disclaimer_prompt` asserting
  the new instruction string is present.
- [x] 3.3 In `backend/tests/test_assistant_agent.py`, add a unit
  test for `_conservative_safety_draft` asserting the new
  `required_point` is present in all three variants (pet safety,
  edibility, generic).
- [x] 3.4 In `backend/tests/test_assistant_agent.py`, add a unit
  test for `_simple_fallback_draft` asserting the new default
  `required_point` is present when the caller passes no explicit
  `required_points`.
- [x] 3.5 In `backend/tests/test_assistant_agent.py`, add a unit
  test for `_recovery_draft_for_answer_generation` asserting the
  new default `required_point` is present.

## 4. Add end-to-end behavior tests for nickname-in-prose

- [x] 4.1 In `backend/tests/test_assistant_agent.py`, add a test
  that passes `plant_hint="Pata"` and a model response that
  contains "Pata" and does not contain the scientific name, and
  asserts the nickname round-trips through the grounded answer
  path. Use `plant_binomial_name="Epipremnum aureum"` and the
  existing `FakeTools` fixture.
- [x] 4.2 In `backend/tests/test_assistant_agent.py`, add a test
  that passes `plant_hint="Pata"` and a model response that uses
  the nickname, and asserts the disclaimed-guidance answer
  contains "Pata" and the diagnostics flag
  `llm_general_guidance_used` is True.
- [x] 4.3 In `backend/tests/test_assistant_agent.py`, add a test
  that passes `plant_hint="Pata"` and triggers the conservative
  safety fallback (e.g. a pet-safety question with insufficient
  evidence), and asserts the rendered answer contains "Pata".

## 5. Add side-channel tests for operational-name-in-investigation

- [x] 5.1 In `backend/tests/test_assistant_agent.py`, add a test
  that passes `plant_hint="Pata"` and
  `plant_binomial_name="Epipremnum aureum"`, runs the grounded
  path, and asserts
  `tools.knowledge_search_kwargs["scientific_name"] ==
  "Epipremnum aureum"` (not `"Pata"`).
- [x] 5.2 In `backend/tests/test_assistant_agent.py`, add a test
  that passes `plant_hint="Pata"` and
  `plant_binomial_name="Epipremnum aureum"`, triggers the web
  fallback by setting `rag_answerable=False` and providing
  `web_results`, and asserts `tools.web_search_query` does not
  contain "Pata".
- [x] 5.3 In `backend/tests/test_assistant_agent.py`, add a test
  that passes `plant_hint="Pata"` and
  `plant_scientific_name="Epipremnum aureum"` and asserts the
  `plant_data` tool call is invoked with the operational name
  (`"Epipremnum aureum"`), not `"Pata"`. Confirm by inspecting
  `tools.plant_data_kwargs` and `tools.plant_data_calls`.

## 6. Replace Spanish fallbacks with language-neutral English placeholders

- [x] 6.1 In `backend/app/assistant/graph.py:2187`, change
  `or "esta planta"` to `or "your plant"` in
  `_simple_fallback_draft`.
- [x] 6.2 In `backend/app/assistant/graph.py:2223`, change
  `or "esta planta"` to `or "your plant"` in
  `_conservative_safety_draft`.
- [x] 6.3 In `backend/app/assistant/graph.py:2335`, change
  `or "esta planta"` to `or "your plant"` in
  `_recovery_draft_for_answer_generation`.
- [x] 6.4 In `backend/app/assistant/graph.py:2458`, change
  `or "esta planta"` to `or "your plant"` in
  `_conservative_safety_answer`.
- [x] 6.5 In `backend/app/assistant/graph.py:2994`, change
  `or "no especificada"` to `or "not specified"` in
  `_general_guidance_with_disclaimer_prompt`.
- [x] 6.6 In `backend/app/assistant/graph.py:3068`, change
  `or "no especificada"` to `or "not specified"` in
  `_grounded_answer_prompt`. (Not enumerated in design.md Decision 6
  at change time; implementation went beyond design; design is now
  updated to list this 6th change.)

## 7. Verification

- [x] 7.1 Run `pytest backend/tests/test_assistant_agent.py -k
  "nickname or grounded_prompt or general_guidance_prompt or
  conservative_safety or simple_fallback or recovery_draft"` and
  confirm all new and existing prompt-builder unit tests pass.
- [x] 7.2 Run the full backend test suite (`pytest
  backend/tests/`) and confirm no regressions. Pay particular
  attention to the existing tests that pass `plant_hint=None` and
  assert the scientific name in the response — they must keep
  passing.
- [x] 7.3 Run the backend linter: `ruff check
  backend/app/assistant/graph.py
  backend/tests/test_assistant_agent.py` and confirm no lint
  regressions.
- [x] 7.4 Automated coverage: `test_nickname_used_in_disclaimed_guidance_answer`
  exercises the disclaimed-guidance path with nickname "Pata" and
  asserts the response contains "Pata". Manual smoke optional.
- [x] 7.5 Automated coverage: `test_nickname_round_trips_through_grounded_answer_path`
  exercises the RAG path with nickname "Pata" and asserts the prompt
  contains "Planta seleccionada: Pata". Manual smoke optional.
- [x] 7.6 Automated coverage: tests for `_simple_fallback_draft`,
  `_conservative_safety_draft`, and `_model_generation_failed_draft`
  assert the "your plant" fallback is used when no nickname is present.
  Manual smoke optional.
