## Context

The backend already exposes internal provider interfaces for model generation, JSON generation, image analysis, embeddings, judge evaluation and search. The current factory returns deterministic mock providers behind a single `provider_profile` setting, which is useful for local and CI but does not support production provider composition.

This change introduces OpenAI-backed providers for the model, vision and judge roles while preserving independent search and embedding configuration. The main constraint is to keep domain services using `app.providers.interfaces` so OpenAI SDK details, credentials and model naming remain isolated to provider implementation and factory code.

## Goals / Non-Goals

**Goals:**

- Configure model, vision, judge, search and embedding provider roles independently.
- Support OpenAI for model generation, image analysis and judge evaluation.
- Keep search and embeddings separately configurable, with no implicit provider coupling when OpenAI is enabled for another role.
- Preserve deterministic mock providers for local and CI runs without real credentials.
- Reuse existing provider-call observability for OpenAI operations with sanitized metadata.

**Non-Goals:**

- Replace existing retrieval, trusted acquisition or LlamaIndex orchestration behavior.
- Require OpenAI for embeddings or search.
- Add frontend configuration surfaces for provider selection.
- Persist provider configuration in the database.

## Decisions

1. Use per-role settings instead of a single provider profile.

   The backend will add explicit settings such as `MODEL_PROVIDER`, `VISION_PROVIDER`, `JUDGE_PROVIDER`, `SEARCH_PROVIDER` and `EMBEDDING_PROVIDER`, plus role-specific model names where the provider needs them. This avoids treating OpenAI enablement as an all-or-nothing profile and prevents generation or vision choices from mutating search or embedding behavior.

   Alternative considered: keep `PROVIDER_PROFILE=openai` and infer all provider roles from it. This is simpler but violates the requirement that model, vision and judge are independently configurable and that search and embeddings remain separate.

2. Keep OpenAI implementations behind existing interfaces.

   OpenAI provider classes will implement the existing `ModelProvider`, `ImageAnalysisProvider` and `JudgeEvaluationProvider` contracts. Domain code will continue to consume the registry fields and result DTOs, with SDK-specific request and response mapping confined to provider modules.

   Alternative considered: call OpenAI directly from assistant, identification or evaluation services. This would make provider replacement harder and bypass existing observability boundaries.

3. Treat judge as its own registry role.

   The registry will expose a dedicated `judge` provider instead of assuming the model provider always handles evaluation. The mock model may still satisfy both roles in tests, but configuration and wiring will allow `JUDGE_PROVIDER=openai` independently from `MODEL_PROVIDER`.

   Alternative considered: reuse `providers.model.judge_response()` everywhere. This keeps fewer fields but couples evaluation quality, cost and credentials to assistant generation.

4. Keep mocks as the safe default for every role.

   Missing or mock provider settings will continue to produce deterministic local providers. OpenAI-backed roles will require an API key at startup or provider construction time only when that role is selected.

   Alternative considered: require OpenAI credentials whenever the OpenAI package is installed. This would break local and CI workflows that intentionally run without real credentials.

5. Reuse provider logging wrappers around SDK calls.

   OpenAI request execution will be wrapped with existing provider-call logging/tracing helpers so failures include provider name, operation, latency and sanitized error information.

   Alternative considered: rely only on SDK exceptions and outer request logging. That would make provider-level failures less diagnosable and inconsistent with current observability requirements.

## Risks / Trade-offs

- Configuration sprawl -> Keep setting names role-oriented and document examples in backend environment templates.
- Misconfigured provider roles -> Fail fast with clear errors only for roles selected as non-mock; keep unselected roles unaffected.
- OpenAI response shape changes -> Isolate parsing in provider classes and cover it with unit tests using mocked SDK responses.
- Cost or latency surprises -> Make judge and vision model names explicit and include operation-level metrics for each call.
- Embedding dimension mismatch -> Do not switch embeddings implicitly; any future OpenAI embedding provider must be configured explicitly and account for vector dimension changes.

## Migration Plan

1. Add per-role settings with defaults matching the current mock behavior.
2. Add OpenAI provider implementations and factory wiring for model, vision and judge roles.
3. Update evaluation runner wiring to use the registry judge provider when no explicit judge provider is injected.
4. Update `.env.example` and deployment examples with role-specific provider settings.
5. Add tests for independent role selection, mock defaults, missing credentials and unchanged search/embedding configuration.

Rollback is configuration-only if mocks remain the default: set affected roles back to `mock` and redeploy.

## Open Questions

- Which OpenAI model names should be the documented defaults for text, vision and judge roles?
- Should judge prompts use the same JSON generation path as model generation or a dedicated structured-output helper inside the OpenAI judge provider?
