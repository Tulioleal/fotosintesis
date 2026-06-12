## Why

Assistant plant-care answers can currently proceed from broad retrieval or fallback evidence without first proving that the evidence covers the user's actual care aspects, especially for multilingual and multi-topic questions. This change makes care answers evidence-gated so the assistant can answer only from validated local or trusted web evidence, target missing information precisely, and avoid using plant nicknames for retrieval or acquisition.

## What Changes

- Add a multilingual classifier step before plant-care retrieval to classify intent, topic, required answer aspects, answer language, plant reference, retrieval need, and confidence.
- Add schema validation, confidence thresholds, and deterministic fallback routing when the classifier fails, times out, returns invalid JSON, or is below the configured acceptance threshold.
- Require confirmed taxonomy before assistant plant-care retrieval, structured lookup, web search, indexing, or embedding, preferring `plant_binomial_name` and falling back only to `plant_scientific_name`.
- Validate retrieved RAG evidence against requested `required_aspects` using hybrid LLM semantic validation plus deterministic guardrails.
- Run trusted web fallback only after local evidence fails to cover all required aspects, and target only the missing aspects.
- Validate web evidence before answer use or persistence, then persist only validated relevant web evidence with filterable aspect metadata.
- Return complete grounded answers, partial non-critical grounded answers, or clear no-evidence fallbacks while preserving the detected answer language.
- Expose bounded diagnostic metadata for care-answer routing and evidence coverage without exposing prompts, raw reasoning, raw evidence text, or provider internals.
- Add regression coverage for multilingual classification, taxonomy-only retrieval/search, aspect validation, targeted web fallback, partial/safety answer behavior, validated web persistence metadata, diagnostics, and classifier fallback.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Assistant plant-care chat must classify multilingual intent/aspects, validate evidence coverage, preserve answer language, enforce safety-sensitive answer gates, and expose bounded diagnostic metadata.
- `knowledge-rag-acquisition`: Runtime retrieval, trusted web fallback, and fallback evidence persistence must use confirmed taxonomy only, target missing required aspects, validate evidence coverage, and persist covered-aspect metadata for validated web evidence.

## Impact

- Backend assistant graph, classifier/routing logic, answer synthesis prompts, evidence sufficiency checks, response metadata, and safety fallback behavior.
- Knowledge/RAG retrieval query construction, trusted web search query construction, web evidence validation, ingestion metadata, vector-index metadata filters, and persistence models if existing metadata fields are insufficient.
- Configuration for classifier model selection and thresholds: classification acceptance, evidence validation, and safety-sensitive validation.
- Backend assistant and knowledge acquisition tests for multilingual routing, taxonomy usage, aspect validation, web fallback targeting, partial/safety answers, persistence metadata, diagnostic metadata, and deterministic classifier fallback.
