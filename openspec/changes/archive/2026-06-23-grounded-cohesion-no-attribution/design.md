## Context

`_grounded_answer_prompt` in `backend/app/assistant/graph.py` (lines 3005-3064) builds the final answer prompt for the assistant. It currently mixes three things that conflict with how source attribution is delivered to the frontend:

1. **In-prose URLs and labeled blocks.** The prompt does not explicitly forbid URLs or "Source-backed / Fuentes / References" blocks in the output, and the existing model output frequently contains `Source-backed: <URL>` strings. These are user-visible artifacts that duplicate the `AssistantChatResponse.sources[]` field already populated by `service.py:137` and structured by `schemas.py:13-17`.
2. **A strict per-sentence separation rule** ("Separa las afirmaciones verificadas de cualquier orientacion general conservadora; no las mezcles en la misma frase", graph.py:3039) that fragments the response and is reinforced by the contradictory rule ("explica la contradiccion con links de las fuentes conflictivas", graph.py:3043) which forces citation-style prose.
3. **An `attribution_instruction` injection** for `evidence_type == "structured_api"` (graph.py:3028-3032) that asks the model to mention structured-API sources in the prose — a third inconsistency where only one evidence type gets a citation instruction in the text.

The frontend already owns the source-rendering channel through `sources[]`. The change moves source handling out of the prose and unifies the response voice around continuous narrative, with the source-backed vs. general-guidance distinction signaled through soft linguistic connectors.

## Goals / Non-Goals

**Goals:**

- Make the grounded response continuous, fluid prose without URLs, institution names, or "Source-backed/Sources/References" blocks.
- Move source attribution entirely to the structured `sources[]` channel; the prompt no longer asks the model to mention sources in the text.
- Use a small, fixed set of linguistic connectors to signal general model guidance inside the narrative, instead of forcing per-sentence separation.
- Make `partial` and `contradictory` states use generic phrasing that does not name or link specific sources.
- Preserve the structured `evidence_type`, limitations, required/covered/missing aspects, support_text, contradiction_text, and source_text inputs to the prompt — these remain internal reasoning material.
- Preserve `llm_general_guidance_used` and the `answer_language` behavior.
- Add regression tests that catch (a) the prompt regressing to allow URLs/source labels and (b) a buggy model output that still emits `Source-backed: https://…` being passed through to the user.

**Non-Goals:**

- Unifying the `_general_guidance_with_disclaimer_prompt` 4-section structure (out of scope; different case — insufficient evidence).
- Frontend changes to how `sources[]` is rendered.
- Refactor of `llm_general_guidance_used` diagnostics.
- Changes to `schemas.py`, `service.py`, `tools.py`, `core/`, `providers/`, or `evaluation/`.
- Rewriting the contradiction detection or the answerability judge.
- Adding new model providers or changing provider selection.

## Decisions

### Decision 1: Single source channel (`sources[]`) in the prose, not in the text

The prompt explicitly prohibits URLs, institution names, and "Source-backed / Sources / References" blocks in the prose. The structured `sources[]` field on the response is the only channel for source metadata. The prompt still feeds `source_text` (truncated to 1200 chars) into the model so it can reason about which claims came from where, but it instructs the model not to echo that metadata in the output.

**Alternatives considered:**

- *Keep citations but add a "do not add Source-backed: <URL> as a separate line, inline them as text" rule.* Rejected: any URL in the prose still leaks source metadata to the text channel and conflicts with the goal of a single source channel. Inline URLs are still URLs.
- *Render sources as a markdown list at the end.* Rejected: the prompt already forbids Markdown and the requirement is plain-text prose.

### Decision 2: Soft linguistic connectors instead of strict per-sentence separation

Replace the rule "Separa las afirmaciones verificadas de cualquier orientacion general conservadora; no las mezcles en la misma frase" with a positive instruction to integrate source-backed and general-guidance content into a continuous narrative and use a fixed set of soft connectors for the general-guidance side: `As a general guideline…`, `In general terms…`, `A common complementary practice is…`, `As a complementary reference…`.

**Rationale:** the per-sentence rule made the response feel disjointed, and the new instruction is easier for the model to satisfy without sacrificing transparency (the connector carries the disclaimer). The model still treats the rest of the text as source-backed.

**Alternatives considered:**

- *Drop the source-backed/general-guidance distinction entirely from the prose.* Rejected: a soft disclaimer is still useful for the user and is required by the assistant-agent spec (`assistant-agent` `Disclaimed general guidance answer mode` and the `llm_general_guidance_used` diagnostics).
- *Use bracket labels like `[general]` or `[source]`.* Rejected: violates the plain-text output rule and adds visual noise.

### Decision 3: Delete the `attribution_instruction` branch

Remove the `if evidence_type == "structured_api": ...` block (graph.py:3028-3032) and the `{attribution_instruction}` interpolation in the closing line (graph.py:3046). `evidence_type` is still passed into the prompt (graph.py:3050) so the model can reason about it internally, but it no longer produces a different output instruction based on type. This eliminates the asymmetric citation behavior between web-RAG and structured-API evidence.

**Alternatives considered:**

- *Generalize the branch to "always mention the first source URL in the text".* Rejected: re-introduces in-prose URLs and conflicts with decision 1.
- *Keep the branch but make it neutral ("evidence type: web_rag" / "evidence type: structured_api" as a visible label).* Rejected: visible labels duplicate diagnostics already in the response and violate the clean-prose goal.

### Decision 4: Generic phrasing for `partial` and `contradictory`

- `partial`: respond with the validated parts and, for aspects that were not corroborated, briefly note "we don't have validated information about them in the consulted sources"; general guidance for those gaps uses one of the connectors.
- `contradictory`: describe the conflict in generic terms (e.g. "there is contradictory information among the consulted sources about X") without naming or linking specific sources; avoid a definitive recommendation; only a single conservative general measure is allowed.

**Rationale:** the previous rules forced the model to write `Source-backed: <URL>` lines, which is exactly what the change is removing. Generic phrasing is consistent with the no-attribution goal and still preserves the limitation signal.

**Alternatives considered:**

- *Keep the URL in the contradictory case as a single line.* Rejected: any URL in the prose violates decision 1.
- *Drop the contradictory disclaimer entirely.* Rejected: contradicts the existing `assistant-agent` `Aspect-gated care answer synthesis` requirement that "the assistant states that the sources conflict" for contradictory evidence — the spec text is updated to use generic phrasing but the disclaimer is preserved.

### Decision 5: Two new tests, one prompt-shape and one end-to-end

- **Prompt-shape test** (`test_grounded_prompt_prohibits_urls_and_source_labels`): parallel to `test_general_guidance_prompt_requires_separation_and_safety_prohibitions` (test_assistant_agent.py:6089). Builds `_grounded_answer_prompt` with synthetic data and asserts:
  - "No menciones URLs" / equivalent prohibition is present.
  - "nombres de instituciones" / equivalent prohibition is present.
  - "Source-backed", "Fuentes", "References" (as output blocks) are prohibited in the output section.
  - The four connectors ("Como pauta general", "En terminos generales", "Una practica habitual complementaria", "Como referencia complementaria" — Spanish) are present.
  - For `evidence_type="structured_api"`, the prompt does NOT contain "fuentes proveedoras estructuradas".
  - Safety prohibitions ("toxicidad", "comestibilidad", "insecticidas") are still present.
  - Non-default `answer_language` is preserved.
  - `evidence_type` is still included as input.
- **End-to-end test** (`test_grounded_response_does_not_leak_sources_to_text`): mocks `tools.generate_text` to return a buggy output like `For a Neon Pothos to do well, place it in medium to low light… Source-backed: https://extension.illinois.edu/houseplants/varieties?utm_source=openai`. Asserts:
  - `result.message.content` does not contain `http`.
  - `result.message.content` does not contain `Source-backed:`.
  - `result.sources` contains the URL and expected metadata.
  - `result.diagnostics` is consistent.
- **Variants** of the end-to-end test: full with one source, full with two sources, partial with general guidance, contradictory, and a case where the model attempts to mention an institution.

**Rationale:** the prompt-shape test guards the prompt itself; the end-to-end test guards the wire between model and user. Without the end-to-end test, a regression in `service.py` (e.g. allowing the model output through verbatim) would not be caught.

**Alternatives considered:**

- *Only the prompt-shape test.* Rejected: doesn't catch a regression where the model ignores the prompt.
- *Only the end-to-end test.* Rejected: doesn't catch a regression in the prompt itself (the prohibitions might silently be removed).
- *A snapshot test of the full prompt.* Rejected: brittle and does not assert intent; the prompt-shape test is more targeted.

## Risks / Trade-offs

- **Risk:** the model ignores the new prohibitions and keeps emitting `Source-backed:` blocks or URLs.
  - **Mitigation:** the end-to-end test mocks a buggy model output and asserts the final response strips it; the prompt explicitly forbids the `Source-backed` string and the `http` substring pattern in the prohibition text.
- **Risk:** users who expect to see source links in the text get confused or feel the assistant is opaque.
  - **Mitigation:** `sources[]` continues to be populated and the frontend renders it. The connector vocabulary gives the user a consistent signal for what is and isn't source-backed. If the frontend does not yet render `sources[]`, raise as a follow-up (out of scope here).
- **Risk:** the source-backed vs. general-guidance distinction becomes too subtle and users do not perceive it.
  - **Mitigation:** the explicit connector list in the prompt gives the model a consistent vocabulary. The `partial` end-to-end test asserts that a connector is present when the model adds general guidance to fill a gap.
- **Risk:** removing the strict per-sentence separation makes the model more willing to mix source-backed and general-guidance claims.
  - **Mitigation:** the prompt still instructs the model to treat the rest of the text as source-backed and to use the connectors only for the general-guidance side. The `llm_general_guidance_used` diagnostic flag and the `sources[]` field remain in place, so the system can still observe when general guidance is used.
- **Risk:** the `assistant-agent` spec text references "shows source links in the text for the conflicting claims" in the `Contradictory evidence` scenario. Updating the spec to use generic phrasing must be carefully scoped so it does not weaken the requirement.
  - **Mitigation:** the spec delta replaces "shows source links in the text for the conflicting claims" with "states that the sources conflict without naming or linking specific sources", preserving the disclaimer without the URL.
