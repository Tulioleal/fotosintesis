## Why

Transient MaaS provider failures such as `503 UNAVAILABLE`, rate limits, timeouts, network errors, empty responses, or invalid structured outputs currently degrade assistant reliability even when another configured provider could complete the same role. The backend already separates provider interfaces by role, so adding role-specific ordered provider chains can improve availability without changing assistant evidence rules or embedding compatibility.

## What Changes

- Add configurable ordered provider chains for model generation, judge evaluation, search, and vision roles, where the first configured provider is attempted first and later configured providers are fallback candidates.
- Treat every provider as order-dependent: Gemini, OpenAI, mock, or any future provider can be the primary attempt or a fallback attempt depending only on the configured role chain.
- Keep embeddings as a single-provider role to preserve vector dimension and index compatibility.
- Preserve existing single-provider environment variables as compatibility fallbacks when provider-chain variables are not configured.
- Add fallback-compatible wrappers for `ModelProvider`, `JudgeEvaluationProvider`, `SearchProvider`, and `ImageAnalysisProvider`.
- Trigger provider fallback only for technical failures such as timeouts, rate limits, service unavailable errors, network failures, empty responses, and invalid structured outputs where applicable.
- Do not trigger provider fallback for semantic outcomes such as an answerability judge returning `insufficient`.
- Treat unusable search output, including empty usable results or internal Gemini grounding redirect-only URLs, as invalid provider output eligible for search fallback.
- Add one internal retry for structured operations such as `generate_json` and `judge_response` before moving to the next provider.
- Add per-role provider attempt timeouts and per-role circuit breaker durations, defaulting circuit breaker opens to 60 seconds.
- Add an in-memory circuit breaker keyed by provider, role, and operation that skips recently failing providers after transient, rate-limit, or timeout failures.
- In production, continue past non-transient provider configuration failures while logging them clearly; in local and development environments, fail clearly to avoid hiding bad setup.
- Record successful provider fallback attempts in diagnostics and conversation metadata without treating them as user-visible tool failures.
- Add structured logs and Prometheus metrics for fallback attempts, fallback successes, provider failures, skipped unhealthy providers, and circuit breaker opens.
- Preserve `/assistant/chat` degraded-response behavior when every provider in a role fails while allowing technical/evaluation flows to surface provider unavailability as failures where appropriate.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `provider-observability`: Add provider-chain configuration, order-dependent primary/fallback behavior, role-specific fallback wrappers, fallback logs and metrics, attempt timeouts, circuit breaker behavior, and compatibility with existing single-provider settings.
- `assistant-agent`: Surface provider fallback diagnostics, persist provider fallback metadata separately from semantic fallback reasons, and preserve safe degraded assistant behavior when every provider in a role fails.
- `gemini-search-provider`: Treat internal redirect-only grounding URLs and other unusable normalized Gemini search outputs as invalid provider output eligible for search fallback.
- `openai-search-provider`: Participate in ordered search provider chains through the existing `SearchProvider` interface, whether configured first or later in the chain.

## Impact

- Affected backend code includes provider interfaces, provider factory and settings, fallback wrappers, Gemini and OpenAI providers, assistant graph/service/tool diagnostics, and observability modules.
- Affected configuration adds `MODEL_PROVIDERS`, `JUDGE_PROVIDERS`, `SEARCH_PROVIDERS`, `VISION_PROVIDERS`, per-role attempt timeout settings, and per-role circuit breaker duration settings while keeping existing single-provider role variables compatible.
- Affected tests include provider registry compatibility and chain tests, fallback recovery tests, circuit breaker tests, assistant diagnostics metadata tests, invalid Gemini search output tests, and all-providers-failed degradation tests.
- Runtime impact is improved availability during provider outages, reduced repeated latency spikes through circuit breaking, and possible additional provider cost only when earlier configured providers fail.
- Public API request contracts are not expected to change; diagnostics metadata may include final provider and provider fallback chain where diagnostics are already returned, and conversation message metadata gains a separate `provider_fallbacks` field.
