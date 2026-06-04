## Context

The assistant now synthesizes final botanical answers with the configured model using grounded prompts. For structured plant-data evidence, provider names are included in prompt metadata and source response fields, but the prompt does not explicitly require the model to mention those providers in the final user-facing answer.

## Goals / Non-Goals

**Goals:**

- Require `structured_api` grounded prompts to tell the model to mention the structured provider sources used.
- Keep provider names available in prompt context without changing the assistant API response shape.
- Add focused regression coverage for structured provider attribution in prompt construction.

**Non-Goals:**

- Do not change provider lookup, source normalization, graph routing or ingestion behavior.
- Do not force provider mentions for RAG or live web answer paths beyond existing source metadata behavior.
- Do not add new provider interfaces or frontend changes.

## Decisions

- Add the attribution requirement in the grounded prompt path using evidence type and existing provider metadata.
  - Rationale: final answer behavior is controlled by model instructions, and structured providers are already passed through `_generate_structured_answer`.
  - Alternative considered: append provider names to model output after generation; rejected because it would mix generated prose with deterministic post-processing and could create awkward duplicated attribution.

- Keep the change scoped to `structured_api` evidence.
  - Rationale: the verification gap is specific to structured API provider attribution, while RAG and live web already preserve source metadata through the API response.
  - Alternative considered: require all answer types to mention all sources inline; rejected because it would broaden behavior beyond the requested fix.

## Risks / Trade-offs

- Model may still omit provider names despite prompt instructions -> Add tests proving the prompt contains an explicit requirement, while source metadata remains available in the API response.
- Prompt wording can become repetitive -> Keep the added instruction short and conditional on `structured_api` evidence.

## Migration Plan

- Update structured API prompt construction.
- Add focused assistant test assertions for the explicit provider-source instruction.
- Roll back by removing the conditional prompt sentence.
