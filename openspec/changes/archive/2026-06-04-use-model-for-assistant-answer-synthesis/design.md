## Context

`AssistantGraph.generate_answer()` currently produces botanical responses by concatenating retrieved evidence, structured provider content or trusted web snippets into fixed strings. The provider registry already exposes a configured model provider, and `KnowledgeAcquisitionService` already uses that provider for knowledge document creation, but the final assistant response path does not use it for synthesis. The change should reuse existing provider seams, source metadata and safety boundaries while improving the quality of final botanical answers.

## Goals / Non-Goals

**Goals:**

- Generate final botanical answers through the configured model provider when RAG, structured plant-data or trusted web evidence is available.
- Provide the model with the user question, selected plant, topic, evidence snippets, evidence type, limitations and source/provider metadata.
- Keep model output grounded in supplied evidence and require uncertainty language for incomplete, degraded or sparse evidence.
- Preserve existing `sources`, `requires_confirmation`, reminder suggestion and tool failure response fields.
- Fall back to deterministic summary text if model generation fails.

**Non-Goals:**

- Do not let the model call tools or change graph routing decisions.
- Do not use the model for prompt-injection bypass, plant disambiguation or unconfirmed plant identification.
- Do not change reminder creation, reminder suggestion or light measurement action semantics.
- Do not introduce a new model provider interface or frontend API schema.

## Decisions

- Add model synthesis behind the assistant tool layer rather than calling the provider directly from every graph branch.
  - Rationale: `AssistantTools` already owns provider access and returns non-blocking tool failures consistently.
  - Alternative considered: call `self.tools.providers.model.generate_text` directly in `AssistantGraph`; rejected because it spreads provider error handling into orchestration code.

- Use one shared synthesis helper for RAG, structured API and trusted web evidence.
  - Rationale: all three paths need the same grounding rules, language constraints, uncertainty handling and source preservation.
  - Alternative considered: keep separate prompt builders per evidence source; rejected unless implementation shows source-specific formatting is needed.

- Keep deterministic fallback builders available.
  - Rationale: model providers can be unavailable, rate-limited or misconfigured, and botanical answers should still degrade safely from available evidence.
  - Alternative considered: fail the response when model generation fails; rejected because current evidence summaries are safer than returning no answer.

- Keep action responses deterministic unless a future requirement explicitly needs explanatory synthesis.
  - Rationale: reminders and light measurement actions have state-changing or tool-result semantics where deterministic completion/failure wording is safer.
  - Alternative considered: route all assistant answers through the model; rejected because it increases risk of claiming failed actions completed.

## Risks / Trade-offs

- Model output may include unsupported claims -> Use strict prompts requiring answers only from supplied evidence and add tests around prompt contents and fallback behavior.
- Model synthesis adds latency and cost -> Invoke it only for final botanical evidence answers, not clarification, unsafe, out-of-domain or deterministic action responses.
- Mock provider output may make tests brittle -> Assert model invocation, prompt inputs, source preservation and fallback behavior rather than exact natural-language text where possible.
- Provider failures could hide useful evidence -> Record model failures as non-blocking tool failures and return deterministic evidence summaries.

## Migration Plan

- Add assistant model synthesis through existing provider wiring.
- Update answer generation branches to attempt model synthesis before deterministic summary fallback.
- Update tests for RAG, structured API and trusted web answer paths.
- Roll back by disabling the synthesis call and retaining deterministic summary generation.
