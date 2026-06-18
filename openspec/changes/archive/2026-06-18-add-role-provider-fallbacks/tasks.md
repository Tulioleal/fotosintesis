## 1. Provider Configuration

- [x] 1.1 Add `MODEL_PROVIDERS`, `JUDGE_PROVIDERS`, `SEARCH_PROVIDERS`, and `VISION_PROVIDERS` settings with ordered-list parsing where provider position determines primary or fallback behavior.
- [x] 1.2 Preserve compatibility by deriving a one-provider chain from `MODEL_PROVIDER`, `JUDGE_PROVIDER`, `SEARCH_PROVIDER`, or `VISION_PROVIDER` when the matching chain setting is absent.
- [x] 1.3 Keep `EMBEDDING_PROVIDER` as single-provider configuration with no embedding chain support.
- [x] 1.4 Add per-role provider attempt timeout settings with documented defaults.
- [x] 1.5 Add per-role circuit breaker duration settings with a 60 second default.

## 2. Fallback Core

- [x] 2.1 Add provider fallback types for role, operation, attempt metadata, final provider metadata, and sanitized failure categories.
- [x] 2.2 Implement transient/technical failure classification for timeouts, rate limits, service unavailable errors, network errors, empty responses, invalid structured output, and unusable search output.
- [x] 2.3 Implement an in-memory circuit breaker keyed by provider name, role, and operation.
- [x] 2.4 Ensure the circuit breaker opens only for transient, timeout, and rate-limit failures.
- [x] 2.5 Ensure open circuits skip unhealthy provider attempts and record skip metadata.

## 3. Fallback Provider Wrappers

- [x] 3.1 Implement `ModelProvider` fallback wrapper for text generation and JSON generation.
- [x] 3.2 Add one same-provider retry for invalid `generate_json` structured output before moving to the next provider.
- [x] 3.3 Implement `JudgeEvaluationProvider` fallback wrapper and one same-provider retry for invalid `judge_response` structured output.
- [x] 3.4 Ensure valid semantic judge results such as `insufficient` do not trigger provider fallback.
- [x] 3.5 Implement `SearchProvider` fallback wrapper with unusable-result detection.
- [x] 3.6 Implement `ImageAnalysisProvider` fallback wrapper.
- [x] 3.7 Apply per-role attempt timeouts inside each fallback wrapper.

## 4. Provider Factory Integration

- [x] 4.1 Update provider factory construction to build role chains for model, judge, search, and vision providers without hard-coding any provider as inherently primary or fallback.
- [x] 4.2 Wrap multi-provider role chains in the appropriate fallback wrapper while preserving direct single-provider behavior where practical.
- [x] 4.3 In local/development environments, fail clearly on non-transient provider configuration errors in configured chains.
- [x] 4.4 In production, log non-transient provider configuration failures and continue with remaining providers when available.
- [x] 4.5 Ensure all-providers-failed errors include sanitized role, operation, provider, and attempt metadata.

## 5. Search Provider Contract Updates

- [x] 5.1 Update Gemini search normalization to reject internal redirect, grounding, or provider-control URLs as unusable search results.
- [x] 5.2 Ensure Gemini search returns usable mixed citations while ignoring malformed or internal-only citations.
- [x] 5.3 Treat Gemini search output with no usable normalized results as invalid provider output for fallback purposes.
- [x] 5.4 Ensure OpenAI search participates in fallback metadata and failure classification through the existing `SearchProvider` contract.
- [x] 5.5 Treat OpenAI search output with no usable citation annotations or normalized results as invalid provider output for fallback purposes.

## 6. Observability

- [x] 6.1 Add structured provider fallback logs for attempts, successes, failures, skipped unhealthy providers, and circuit breaker opens.
- [x] 6.2 Add Prometheus metrics for fallback attempts, fallback successes, provider failures, skipped unhealthy providers, and circuit breaker opens.
- [x] 6.3 Ensure logs, metrics, and diagnostics exclude credentials, raw prompts, full model responses, and raw provider payloads.
- [x] 6.4 Expose final provider and attempted provider chain in assistant diagnostics where diagnostics are already returned.

## 7. Assistant Integration

- [x] 7.1 Persist technical provider fallback metadata under `provider_fallbacks` in assistant message metadata.
- [x] 7.2 Keep provider fallback metadata separate from semantic fallback reasons such as `web_search_used`, RAG insufficiency, and conservative safety fallback.
- [x] 7.3 Preserve existing `/assistant/chat` degraded-response behavior when all model providers fail.
- [x] 7.4 Preserve existing minimal Spanish emergency response behavior when fallback rendering cannot use any model provider.
- [x] 7.5 Allow non-chat technical and evaluation flows to surface provider-unavailable failures with sanitized attempt metadata.

## 8. Tests

- [x] 8.1 Add provider registry tests for single-provider compatibility, ordered chain construction, and provider-agnostic primary/fallback ordering.
- [x] 8.2 Add fallback wrapper tests for transient failure recovery, invalid structured-output retry, semantic insufficient non-fallback, and all-providers-failed behavior.
- [x] 8.3 Add circuit breaker tests for opening, skipping unhealthy providers, expiry, and non-transient failures not opening the circuit.
- [x] 8.4 Add configuration failure tests for local/development fatal behavior and production continue-with-logs behavior.
- [x] 8.5 Add assistant diagnostics tests for `provider_fallbacks`, final provider metadata, and separation from semantic fallback reasons.
- [x] 8.6 Add Gemini search tests for redirect-only/internal grounding URLs, no usable normalized results, and mixed usable/unusable citations.
- [x] 8.7 Add search provider tests showing Gemini and OpenAI can each be configured first or later in `SEARCH_PROVIDERS` and preserve the same `SearchProvider` contract.
- [x] 8.8 Run the relevant backend test suite and targeted assistant/provider tests.
