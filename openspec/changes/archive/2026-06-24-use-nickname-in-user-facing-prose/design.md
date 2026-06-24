## Context

The assistant's plant-care answer pipeline has two plant-name surfaces:

- **Operational plant name** — the binomial (preferred), a binomial derived
  from the full scientific name, or the scientific name as a last resort.
  This name drives every investigation operation: `knowledge_search`,
  `trusted_web_search`, `plant_data_lookup`, embeddings, indexing, and
  ingestion queries. It is computed by `operational_plant_name(...)` in
  `backend/app/assistant/graph.py` and resolved per state via
  `_operational_name_for_tools(state)`.

- **Display plant name** — the value the assistant uses to address the plant
  in user-facing prose. It is computed by `display_plant_name(...)` with
  priority `request.plant -> request.plant_scientific_name ->
  request.plant_binomial_name`, or by `_display_plant(selected_plant)`
  which prefers `selected.nickname -> selected.common_name ->
  selected.scientific_name`. The selected-plant path is only used when
  `_display_name_for_answer(state)` finds no `display_plant_name` in
  state. The display name is passed to user-facing prompt builders as
  the `plant_name` argument.

The two surfaces are correctly separated at the data layer: the nickname
never reaches RAG, web search, structured lookup, embeddings, or
ingestion. The bug is at the prompt layer: the user-facing prompts
(`_grounded_answer_prompt`, `_general_guidance_with_disclaimer_prompt`,
the conservative safety fallback template, the simple fallback draft
defaults, and the recovery draft for answer generation) all pass the
display name to the model under a label like `Planta seleccionada:
<nickname>` and then trust the model to keep using it. When the model
sees a common or scientific name in the evidence, taxonomy context, or
source metadata, it often substitutes that name into the user-facing
prose and drops the nickname.

The frontend already prefers the nickname: `frontend/src/components/garden/GardenDetail.tsx`
sends `plant=nickname -> selected_alias -> common_name -> scientific_name`
to the assistant URL. The backend is the layer that fails to honor it.

The change is prompt-only on the model side. No data flow, schema, or
investigation path changes.

## Goals / Non-Goals

**Goals:**

- The model addresses the plant in user-facing prose using the value
  supplied as the display plant name (the nickname / display name from
  the request or the saved-plant's nickname from the selected garden
  plant).
- The operational / scientific / binomial names remain in the prompt
  context (so the model still knows the plant) but MUST NOT replace the
  display name as the leading plant name in the prose.
- Investigation operations (RAG, web search, structured lookup,
  embeddings, indexing, ingestion) keep using the operational name.
  The nickname MUST NOT be sent to any of them.
- Display-name priority is unchanged. `request.plant` wins, then the
  saved-plant's nickname, then the operational name.
- Regression tests pin the new behavior at three layers: prompt
  instruction string present, end-to-end model output preserved, and
  side-channel operational name only in investigation tools.

**Non-Goals:**

- No post-processing filter on the model output. The prose is allowed
  to mention the common or scientific name when the user does, when
  the evidence explicitly contains the nickname, or when the user asks
  about the plant by its scientific name. The instruction is about
  which name the model leads with and addresses the user with, not
  about banning every plant name in the response.
- No change to `display_plant_name` priority, `operational_plant_name`
  resolution, `_display_name_for_answer`, the saved-plant lookup, the
  frontend `buildAssistantHref` builders, or the classifier contract's
  `plant_reference` field semantics.
- No frontend, mobile, docs, database, dependency, or provider change.
- No data migration.

## Decisions

### Decision 1: The prompt instruction is the lever, not a post-hoc filter

The user-facing prompt builders gain a short paragraph that tells the
model to use the value labeled as the selected plant in the response
and to never replace it with the common / scientific / binomial name
from the evidence, taxonomy context, or source metadata. The scientific
and binomial names in `Contexto adicional` are framed as retrieval and
taxonomy context only, and MUST NOT appear in the prose as the plant's
name.

**Alternatives considered:**

- Post-process the model output to strip occurrences of the common /
  scientific name. Rejected: brittle, would corrupt legitimate
  references (e.g. when the user explicitly says "my Pothos", when the
  evidence explicitly names the plant by its scientific name, or when
  the user asks about the plant's scientific name). The instruction
  about which name to lead with is the right level of control.
- Reorder the prompt so the display name appears after the evidence.
  Rejected: ordering does not change the model's preference, and
  evidence-first ordering is needed for source-grounding semantics in
  the grounded answer prompt.
- Strip the scientific and binomial names from the prompt entirely.
  Rejected: the model still needs the operational name to ground its
  answer in the evidence; removing it would degrade answer quality.

### Decision 2: Apply the instruction in all five user-facing sites

The five sites that emit user-facing prose with a `plant_name` are:

1. `_grounded_answer_prompt` (graph.py around line 3029)
2. `_general_guidance_with_disclaimer_prompt` (graph.py around line 2939)
3. `_conservative_safety_draft` (graph.py around line 2215) — three
   variants: pet safety, edibility, generic
4. `_simple_fallback_draft` (graph.py around line 2179) — default
   `required_point` when the caller passes no explicit `required_points`
5. `_recovery_draft_for_answer_generation` (graph.py around line 2341)
   — default `required_point` so a recovered answer also honors the
   nickname

Each site receives the instruction in the form that fits the existing
prompt tone (paragraph in the long prompts, `required_point` in the
fallback drafts).

Note: the language of the instruction matches the language of the
surrounding prompt. The 2 long prompts (sites 1, 2) are in Spanish at
the time of this change, so the instruction there is in Spanish.
The sibling `backend-english-and-llm-intent` change translates the
surrounding prompt to English, which carries the instruction with it.
The 3 fallback drafts are in English, so the instruction there is in
English.

**Alternatives considered:**

- Apply the instruction only to the two main answer prompts. Rejected:
  the conservative safety fallback, simple fallback, and recovery
  draft all emit user-facing prose with the same `plant_name` contract
  and exhibit the same substitution behavior. The user explicitly
  asked for all paths.
- Add the instruction in a single shared helper that the five sites
  call. Rejected: each site has a different prompt structure (long
  paragraph vs `required_point` list). The duplication is small (a
  single sentence) and easier to read in place.

### Decision 3: Display-name priority is unchanged

`display_plant_name()` keeps priority `request.plant ->
request.plant_scientific_name -> request.plant_binomial_name`.
`_display_name_for_answer(state)` keeps priority
`state.display_plant_name -> _display_plant(selected_plant)`. The
frontend keeps sending `plant=nickname -> selected_alias ->
common_name -> scientific_name`.

**Alternatives considered:**

- Override the display name with the saved-plant's nickname from the
  selected garden plant whenever one is present, even if the request
  sent a different value. Rejected: the request is the source of
  truth for what the user wants the assistant to call the plant in
  this turn; the saved-plant nickname is only the fallback when the
  request is silent.

### Decision 4: The classifier `plant_reference` keeps carrying the nickname

The classifier's `plant_reference` field already carries the nickname
or plant reference from the user message. It is consumed only as a
reference signal (for classifier output and for matching the saved
plant in the garden). It is not used for retrieval, web search, or
ingestion. The new requirement makes this split explicit in the spec
so a future change cannot accidentally route the nickname to retrieval.

**Alternatives considered:**

- Strip the nickname from the classifier prompt entirely. Rejected:
  the classifier uses it as a reference signal to anchor the
  `topic` and `required_aspects` choices to the plant the user is
  actually asking about.

### Decision 5: Test coverage at three layers

Three test layers pin the new behavior:

- **Prompt-builder unit tests** assert the new instruction string is
  present in each of the five user-facing prompt / draft builders.
  These catch regressions where a prompt refactor accidentally drops
  the instruction.
- **End-to-end behavior tests** assert the nickname round-trips
  through the model response in the grounded, disclaimed, and
  conservative safety paths. The model output is fed in directly; the
  tests assert it is preserved end-to-end.
- **Side-channel tests** assert the operational name is the only name
  passed to `tools.knowledge_search_kwargs.scientific_name`,
  `tools.web_search_query`, and `tools.plant_data_kwargs`. These catch
  regressions where a future change accidentally routes the nickname
  to investigation.

**Alternatives considered:**

- Only prompt-builder unit tests. Rejected: they do not prove the
  end-to-end behavior or the investigation guarantee.
- Only end-to-end behavior tests. Rejected: they do not pin the
  prompt text, so a refactor that drops the instruction but leaves
  the same behavior on the test inputs would not be caught.
- Only side-channel tests. Rejected: they do not cover the model
  side at all.

### Decision 6: Language-neutral English fallback when display name is absent

When `display_plant_name` is absent (no `request.plant`, no selected
garden plant with a nickname), the five prompt sites fall back to a
language-neutral English placeholder rather than a Spanish phrase. The
four call sites use `"your plant"` and the disclaimed-guidance prompt
site uses `"not specified"`. This prevents two failure modes:

- **Spanish drift.** If the model sees a Spanish phrase as the plant's
  name, it is more likely to lean Spanish in the response even when
  `answer_language` specifies another language, or to mirror the Spanish
  syntax in ways that clash with the English prompt body.
- **Phantom nickname.** The model treats "esta planta" as a nickname
  and dutifully echoes it in the prose ("tu esta planta"), which is
  grammatically awkward and breaks the goal that the fallback is a
  generic reference, not a name.

`"your plant"` is short and language-neutral; the model translates it
correctly into Spanish, English, Italian, or any other `answer_language`
without any per-language code or Spanish residue. It also aligns with the
`backend-english-and-llm-intent` change's goal of removing Spanish
residue from prompts.

The six string changes are:

- `graph.py:2187` — `or "esta planta"` → `or "your plant"`
- `graph.py:2223` — `or "esta planta"` → `or "your plant"`
- `graph.py:2335` — `or "esta planta"` → `or "your plant"`
- `graph.py:2458` — `or "esta planta"` → `or "your plant"`
- `graph.py:3006` — `or "no especificada"` → `or "not specified"`
- `graph.py:3068` — `or "no especificada"` → `or "not specified"` (in `_grounded_answer_prompt`)

Each change has a matching regression test that asserts the English
string is what the model receives in the prompt.

**Alternatives considered:**

- **Language-aware fallback** (pick the right Spanish/English/Italian
  phrase per `answer_language`). Rejected: the LLM translates English
  well, so the gain is small; per-language strings introduce a lookup
  that is easy to leave incomplete in tests; and Option A (plain English)
  is strictly simpler with no loss of quality.
- **Drop the placeholder entirely** (pass `None`, omit the line).
  Rejected: the instruction "use the value in Planta seleccionada"
  needs a fallback clause ("if no display name is available, use a
  generic reference like 'your plant'"), which adds complexity; keeping
  the placeholder with the explicit English text is clearer.

## Risks / Trade-offs

- [Risk] The model may still occasionally slip the common or scientific
  name into the prose despite the explicit prompt instruction.
  → Mitigation: the instruction is short, direct, and repeated across
  all five user-facing sites. Prompt-builder unit tests assert it is
  present. The end-to-end behavior tests assert the model output is
  preserved verbatim, so any prompt regression that would let the
  substitution behavior in is caught by the prompt-builder tests
  before it can affect the model output. There is no post-hoc filter,
  by design — the prose is allowed to mention other names when the
  user does or the evidence explicitly does.

- [Risk] Adding the instruction to every prompt and draft increases
  token count slightly on every assistant turn. → Mitigation: the
  instruction is one or two short sentences. The token overhead is
  bounded and does not affect routing or retrieval cost.

- [Risk] A future change might add a new user-facing prompt that
  emits prose with `plant_name` and forget the new instruction.
  → Mitigation: the new top-level spec requirement
  `User-facing plant naming in response prose` makes the rule explicit
  and discoverable; reviewers can check any new prompt against it.

- [Risk] The investigation guarantee depends on `_operational_name_for_tools`
  being the only name passed to `knowledge_search`,
  `trusted_web_search`, `plant_data_lookup`, embeddings, and
  ingestion. A future refactor could accidentally pass `display_plant_name`.
  → Mitigation: the side-channel tests assert each of those tools
  receives the operational name and not the display name, and the new
  spec scenario explicitly forbids the display name from being sent to
  those operations.

## Migration Plan

This change ships as a single deployable release with no data migration.
The steps are:

1. **Code change** — add the instruction paragraph / `required_point`
   to the five user-facing prompt / draft builders in
   `backend/app/assistant/graph.py`.
2. **Test change** — add the prompt-builder unit tests, the
   end-to-end behavior tests, and the side-channel tests in
   `backend/tests/test_assistant_agent.py`.
3. **Run the full test suite** — `pytest backend/tests/`. The existing
   tests that pass `plant_hint=None` and assert the scientific name in
   the response must keep passing; the new behavior tests cover the
   case where `plant_hint` is set to a nickname.
4. **Manual smoke** — open the assistant from a garden plant with the
   nickname "Pata", ask a question that lands in the disclaimed
   guidance path, and confirm the response uses "Pata" rather than
   the common or scientific name.
5. **Rollback** — revert the single commit. There is no data
   migration and no schema change, so a rollback is a clean revert.

## Open Questions

None. The change is well-scoped, the data flow is already correct, and
the lever is a single short instruction applied at five known sites.
