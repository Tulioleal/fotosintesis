## Why

Fotosintesis needs a Gemini-backed provider option for model generation, plant image analysis and LLM-as-judge evaluation without coupling those roles to OpenAI or changing retrieval providers. Adding Gemini behind the existing provider interfaces improves provider portability while preserving deterministic local and CI behavior.

## What Changes

- Add Gemini-backed implementations for model generation, JSON generation, plant image analysis and judge evaluation.
- Allow `MODEL_PROVIDER=gemini`, `VISION_PROVIDER=gemini` and `JUDGE_PROVIDER=gemini` through the existing independent role provider settings.
- Add one shared `GEMINI_API_KEY` setting and role-specific Gemini model settings for text, vision and judge roles.
- Add the official `google-genai` Python SDK as a backend dependency for selected Gemini roles.
- Keep Gemini search and Gemini embeddings out of scope so trusted web search and pgvector embedding dimensions remain unchanged.
- Keep domain services dependent on internal provider interfaces rather than Gemini SDK types.
- Preserve mock providers as the default for local and CI runs without Gemini credentials.
- Extend provider observability so Gemini calls are logged, traced and measured with sanitized provider-call metadata.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `provider-observability`: Add Gemini model, vision and judge provider role requirements, independent configuration behavior, credential failure behavior and observability expectations.
- `plant-identification-taxonomy`: Clarify that the vision provider interface may be backed by Gemini while preserving the existing plant candidate contract.
- `evaluation-pipeline`: Clarify that LLM-as-judge evaluation can use the configured Gemini judge provider through the existing judge interface.

## Impact

- Backend provider configuration and dependency wiring.
- Internal model, vision and judge provider implementations.
- Backend environment examples and deployment configuration examples.
- Tests for provider factory selection, credential failures, Gemini response mapping and observability wrapping.
- No frontend API changes, database migrations, Gemini search provider or Gemini embedding provider.
