## Context

The backend already exposes internal provider interfaces for model generation, JSON generation, image analysis, embeddings, search and judge evaluation. OpenAI providers are wired through independent role settings, while domain services consume `app.providers.interfaces` and internal result DTOs instead of SDK-specific types.

This change adds Gemini as another provider implementation for model, vision and judge roles. The design constraint is to preserve the existing role-based registry and avoid changing retrieval, trusted web search or pgvector embedding behavior.

## Goals / Non-Goals

**Goals:**

- Support `MODEL_PROVIDER=gemini`, `VISION_PROVIDER=gemini` and `JUDGE_PROVIDER=gemini` independently.
- Use the Gemini Developer API with a shared `GEMINI_API_KEY` setting.
- Add role-specific Gemini model settings for text, vision and judge roles with Flash-class defaults.
- Keep Gemini SDK details isolated to provider implementation and factory code.
- Map Gemini responses into existing `TextGenerationResult`, `JsonGenerationResult`, `ImageAnalysisResult` and `JudgeResult` DTOs.
- Wrap Gemini SDK calls with existing provider-call observability.
- Keep deterministic mocks as the default for local and CI runs.

**Non-Goals:**

- Support Vertex AI configuration.
- Add Gemini search or Gemini embeddings.
- Change vector dimensions, existing knowledge retrieval or trusted web search behavior.
- Add frontend provider selection or database-backed provider configuration.
- Add live Gemini integration tests to CI.
- Add a new global `LLM_PROVIDER` or Gemini-specific domain interface.

## Decisions

1. Reuse existing provider interfaces.

   Gemini providers will implement `ModelProvider`, `ImageAnalysisProvider` and `JudgeEvaluationProvider`. Domain code will continue using the provider registry fields and internal result types. This keeps Gemini interchangeable with OpenAI and mocks without introducing provider-specific branching.

   Alternative considered: add a new LLM interface or Gemini-specific interface. This would make the change larger and couple domain code to provider capabilities that are not required by the current product flows.

2. Use independent role selectors with value `gemini`.

   The factory will recognize `gemini` for model, vision and judge roles only. Search and embedding provider builders will not accept Gemini in this change. This matches the current OpenAI role-independence pattern and prevents generation choices from altering retrieval behavior.

   Alternative considered: add a single `LLM_PROVIDER` setting. This would conflict with the existing per-role provider model and make it easier to accidentally couple judge, vision and runtime generation.

3. Use a shared Gemini API key and role-specific model settings.

   `GEMINI_API_KEY` will be required only when a selected role uses Gemini. `GEMINI_TEXT_MODEL`, `GEMINI_VISION_MODEL` and `GEMINI_JUDGE_MODEL` will allow cost, latency and quality to be tuned independently per role. Defaults should use a Flash-class Gemini model and remain configurable.

   Alternative considered: per-role Gemini API keys. There is no current deployment requirement for separate keys, so a shared key keeps configuration smaller.

4. Add the official `google-genai` SDK as a backend dependency.

   Adding the SDK to base backend dependencies makes Gemini deployments reproducible and avoids hidden runtime install requirements. Provider construction should still fail clearly only for selected Gemini roles when credentials are missing or SDK import fails.

   Alternative considered: lazy optional dependency only. That would reduce base dependencies but make deployments easier to misconfigure.

5. Keep strict JSON behavior inside the Gemini model provider.

   `generate_json(prompt, schema)` will request structured JSON using the supplied schema when supported by the SDK, parse the response as a JSON object and raise `GeminiProviderError` if the response is invalid or not an object. The provider will include schema metadata in the internal result without leaking SDK response types.

   Alternative considered: best-effort JSON parsing. That would be less reliable for acquisition and judge flows that expect structured objects.

6. Keep plant vision scoped to existing candidate output.

   Gemini vision will use the existing plant-identification prompt shape and map responses into up to three `PlantCandidate` values with scientific name, optional common name, confidence label, optional score and visible traits.

   Alternative considered: introduce a broader general image analysis contract. Current app behavior only needs plant identification, so expanding the contract would add unnecessary scope.

7. Normalize provider failures with `GeminiProviderError`.

   SDK import failures, SDK call failures and response parsing failures will be wrapped or surfaced as `GeminiProviderError`. Existing assistant, identification and evaluation flows can then apply their current degradation behavior without Gemini-specific fallback logic.

   Alternative considered: automatically fall back to OpenAI or mock when Gemini fails. That could hide production misconfiguration, change cost unexpectedly and make evaluation results harder to interpret.

## Risks / Trade-offs

- Gemini SDK response shape or structured-output options differ from OpenAI -> Keep SDK calls and parsing isolated in `app.providers.gemini` and cover them with fake SDK unit tests.
- Exact Flash-class model IDs may change -> Keep model names configurable and verify defaults against current Gemini SDK/docs during implementation.
- Strict schema mapping may require SDK-specific conversion -> Confine schema conversion to `GeminiModelProvider.generate_json` so domain code remains unchanged.
- Additional backend dependency increases install surface -> Accept this because Gemini is a first-class provider option and selected roles should work from project dependencies.
- Provider role misconfiguration can fail startup or provider construction -> Fail fast with clear selected-role credential errors while preserving mock defaults for unselected roles.

## Migration Plan

1. Add Gemini settings with mock-preserving defaults and update environment examples.
2. Add `google-genai` to backend dependencies.
3. Add Gemini provider classes and factory wiring for model, vision and judge roles.
4. Add deterministic mocked SDK tests for provider construction, response mapping, error handling and observability.
5. Deploy with existing mock/OpenAI settings unchanged.
6. Enable Gemini per role by setting the relevant provider selector to `gemini`, providing `GEMINI_API_KEY` and optionally overriding role model names.

Rollback is configuration-only for deployments that keep existing providers available: set affected roles back to `mock` or `openai` and redeploy.

## Open Questions

None. `gemini-2.5-flash` is the configured Flash-class default for text, vision and judge roles.
