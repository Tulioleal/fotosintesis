## Why

The assistant's plant-care answer pipeline already separates the operational
plant name (binomial or scientific, used for RAG, web search, structured
lookup, embeddings, and indexing) from the display plant name (nickname /
display name / common name, used for user-facing prose). The investigation
side is correct: the operational name is never the nickname, so evidence
queries stay stable and language-neutral.

The response side, however, currently passes the display name to the model
as a labeled value and then trusts the model to use it. In practice, when
the model's evidence, taxonomy context, or source metadata contains a
common or scientific name, the model often substitutes that name into the
user-facing prose and drops the nickname. For example, a user who names a
Neon Pothos "Pata" receives answers that say "tu planta Neon Pothos"
instead of "tu Pata", which breaks the personal relationship the nickname
implies and makes the assistant feel generic. This is observable in
`general_guidance_with_disclaimer` answers, grounded answers, conservative
safety fallbacks, and the simple fallback drafts that follow the same
`plant_name` contract.

The change makes the model honor the nickname as the user-facing plant
name in all assistant prose while preserving every existing guarantee
about the investigation side: the operational name continues to drive
retrieval, web search, structured lookup, embeddings, and indexing, and
the nickname is never sent to those operations.

## What Changes

- Instruct the model in the user-facing answer prompts to refer to the
  plant using the value supplied as the selected plant (the nickname /
  display name) and to never replace that value with the common name,
  the scientific name, or the binomial from the evidence, taxonomy
  context, or source metadata. Apply this instruction in
  `_grounded_answer_prompt`, `_general_guidance_with_disclaimer_prompt`,
  the conservative safety fallback template, the simple fallback draft
  defaults, and the recovery draft for answer generation.
- Clarify in the spec that the `plant_reference` field in the classifier
  contract continues to carry the nickname as a reference signal only,
  and that investigation operations (RAG, web search, structured lookup,
  embeddings, indexing, ingestion) MUST keep using the operational plant
  name. The nickname MUST NOT be sent to those operations.
- Make the display-name priority explicit and unchanged: `request.plant`
  (the frontend's nickname -> selected_alias -> common_name ->
  scientific_name value) wins, then the saved-plant's nickname from the
  selected garden plant, then the operational name. No new source of
  truth is introduced.
- Add regression tests that assert the nickname round-trips through the
  user-facing prose, that the operational name is still the only name
  passed to investigation tools, and that the prompt-builder unit tests
  pin the new instruction in place.
- Do NOT add a post-processing filter that strips the common or
  scientific name from the model output. The prompt is the lever; the
  prose is allowed to mention the common or scientific name when the
  user does, the evidence explicitly contains the nickname, or the user
  asks about the plant by its scientific name. The instruction is about
  which name the model leads with and addresses the user with, not
  about banning every plant name in the response.
- Do NOT change the investigation path, the display-name priority, the
  frontend link builders, or the operational/scientific name resolution.
  The architecture split is already correct; the missing piece is the
  prompt instruction that binds the model to the display name.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Add a top-level requirement `User-facing plant
  naming in response prose` that binds the model to the value in
  `display_plant_name` (the nickname / display name from the request)
  and treats the operational / scientific / binomial names as
  retrieval context only. Scenarios cover the disclaimed guidance path,
  the grounded answer path, the conservative safety path, the simple
  fallback path, and a scenario that explicitly forbids the nickname
  from being sent to RAG, web search, structured lookup, embeddings,
  or indexing.

## Impact

- Affected backend code: `backend/app/assistant/graph.py` for the five
  prompt / fallback builders that emit user-facing prose with a
  `plant_name`. No new modules, no schema change.
- Affected backend tests: `backend/tests/test_assistant_agent.py` for
  prompt-builder unit tests, end-to-end nickname-in-prose behavior
  tests, and side-channel operational-name-in-investigation tests.
- No frontend, mobile, docs, database, dependency, or provider change.
- No data migration. Existing persisted assistant messages stay
  readable; new messages will use the nickname more consistently where
  one was supplied.
- Risk: the model may occasionally still slip the common or scientific
  name into the prose despite the prompt. This risk is bounded by the
  prompt instruction being explicit and by the new prompt-builder unit
  tests that assert the instruction is present. There is no post-hoc
  filter, by design.
