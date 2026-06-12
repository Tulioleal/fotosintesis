## Context

The assistant graph already separates routing, retrieval, answerability evaluation, structured data lookup, trusted web fallback, and grounded answer generation. However, several fallback paths still return final user-facing Spanish prose directly from graph nodes and helper functions. This includes clarification, unsafe/out-of-domain handling, missing taxonomy, missing reminder data, action failures, insufficient evidence, conservative safety guidance, and deterministic summaries used when model generation fails.

The existing `answer_language` field is populated by classification and used by grounded answer prompts, but it is not consistently applied to fallback responses. The current deterministic language detector is keyword-based and does not scale beyond a few simple phrases. The desired behavior is to let the LLM classifier determine the real language used by the user message, while ignoring instructions that ask for a different output language, and to default to Spanish when classification is unavailable.

## Goals / Non-Goals

**Goals:**

- Centralize user-facing fallback response rendering behind one abstraction.
- Represent fallback responses as structured intents with allowed facts and constraints before rendering final prose.
- Use the classifier-provided `answer_language` for fallback rendering whenever classification succeeds.
- Remove deterministic language detection and default deterministic classification language fields to Spanish.
- Preserve deterministic decisions for routing, safety, answerability, evidence validation, source selection, and fallback intent selection.
- Provide a minimal Spanish emergency response with no links when fallback response rendering fails.
- Keep assistant API response shape stable unless implementation needs purely internal metadata.

**Non-Goals:**

- Do not allow the fallback renderer to decide whether evidence is sufficient.
- Do not allow the fallback renderer to add botanical facts, care recommendations, sources, or links that were not supplied by validated state.
- Do not change RAG acquisition, embeddings, structured plant-data lookup, trusted web search, or answerability judge semantics.
- Do not introduce a new model provider or external dependency.
- Do not implement full translation infrastructure or user language preferences in this change.

## Decisions

1. Use a structured fallback response draft before final text generation.

   Graph nodes should build a draft containing a fallback intent, `answer_language`, allowed facts, required points, prohibited points, and rendering constraints such as plain text and no unsupported claims. The draft is the contract between deterministic orchestration and model rendering.

   Alternative considered: keep hardcoded translated templates per language. This would be predictable but increases maintenance and does not solve scattered fallback prose. A model-rendered draft keeps behavior centralized while preserving deterministic fallback decisions.

2. Render all user-facing fallback paths through a centralized graph method.

   A method such as `_generate_fallback_response(state, draft)` should call the existing text model provider with a strict prompt. The prompt should state that the model may only verbalize the supplied draft, must respect `answer_language`, must output plain text, and must not introduce links, unsupported facts, internal fallback reason codes, or additional recommendations.

   Alternative considered: route only multilingual clarification paths through the renderer. This leaves safety, action failures, and model-failure summaries inconsistent, so it does not meet the architectural cleanup goal.

3. Keep a minimal Spanish emergency template for renderer failure.

   If fallback rendering fails, times out through the provider, or returns empty output, the assistant should return a short Spanish response that avoids links and unsupported botanical content. The original rendering failure should be recorded in `tool_failures` when possible.

   Alternative considered: fail the request or return no answer. This degrades core assistant usability and makes fallback routes unreliable exactly when tools are already degraded.

4. Remove deterministic language detection entirely.

   Successful LLM classification is the only source of non-default `language` and `answer_language`. Deterministic classification remains for intent/topic/aspect routing only and always sets both language fields to `es`.

   Alternative considered: keep keyword language detection as a last resort. The user explicitly chose to remove it and accept Spanish as the degraded default.

5. Treat language-switch instructions as ignored for `answer_language`.

   The classifier prompt should instruct the model to infer `answer_language` from the actual language used in the message, not from instructions requesting another output language. For example, Spanish content that says “respond in English” should still classify `answer_language` as Spanish.

   Alternative considered: obey explicit response-language instructions. This was rejected because the desired behavior is language-by-message-context only.

6. Keep safety policy deterministic and allow only linguistic rendering.

   Conservative pet toxicity and human edibility fallbacks should remain selected by deterministic safety logic when direct evidence is unavailable. The fallback renderer can adapt wording and language, but the draft must include required safety points and prohibited claims.

   Alternative considered: let the renderer decide conservative language freely. This risks unsafe claims and makes safety tests weaker.

## Risks / Trade-offs

- Model-rendered fallbacks may vary wording between runs → Tests should assert required semantic content and constraints rather than exact prose, except for emergency template behavior.
- Rendering every fallback can increase latency and model usage → Keep prompts compact and use existing provider infrastructure; emergency template remains available on failure.
- The renderer may ignore constraints → Prompts must be explicit, and tests should cover no-link, no-internal-code, and safety-required-point behavior. Safety decisions must remain outside the renderer.
- Removing deterministic language detection means classifier failure always degrades to Spanish → This is an accepted product trade-off and should be covered by tests.
- Some existing fallback helpers include evidence snippets → Drafts must distinguish validated facts from unsupported or diagnostic information so the renderer does not overstate evidence.

## Migration Plan

1. Add the fallback response draft contract and centralized renderer behind existing graph behavior.
2. Convert fallback paths incrementally within the same change, keeping existing route decisions intact.
3. Remove `_detect_language()` and update deterministic classification language defaults.
4. Update classifier prompt language rules.
5. Add and update tests for language selection, fallback rendering, renderer failure, and safety constraints.
6. Rollback strategy: restore direct fallback strings and deterministic language detection if the renderer introduces regressions before release.

## Open Questions

None. The current agreed behavior is to ignore user requests to answer in a different language and derive `answer_language` from the language actually used in the message.
