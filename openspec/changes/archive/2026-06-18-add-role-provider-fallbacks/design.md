## Context

The backend already has role-specific provider interfaces and independent provider configuration for model generation, vision analysis, judge evaluation, search, and embeddings. Gemini and OpenAI implementations exist for most roles, but runtime calls currently use the selected provider directly, so a transient failure in whichever provider is configured for a role can surface as a tool or model failure even when another configured provider could satisfy the same role.

The assistant also has semantic fallback paths such as RAG-to-web routing. This change keeps those semantic decisions separate from infrastructure fallback: provider fallback only handles technical failures and MUST NOT reinterpret answerability decisions such as `insufficient`.

Embeddings remain deliberately excluded from provider chains because provider changes can alter vector dimensions, distance distributions, and index compatibility.

## Goals / Non-Goals

**Goals:**

- Add per-role ordered provider chains for model, judge, search, and vision providers, where primary and fallback behavior is determined only by chain order.
- Preserve existing single-provider settings when new chain settings are absent.
- Retry structured provider operations once before failing over to the next provider.
- Bound each provider attempt with role-specific timeouts.
- Skip recently unhealthy providers through an in-memory circuit breaker keyed by role, provider, and operation.
- Record technical fallback metadata separately from assistant semantic fallback reasons.
- Emit structured logs and Prometheus metrics for fallback attempts, successes, failures, skipped providers, and circuit breaker opens.
- Preserve safe degraded `/assistant/chat` behavior when every provider in a role fails.

**Non-Goals:**

- Changing embedding provider compatibility, vector indexes, or embedding fallback behavior.
- Changing answerability rules, evidence thresholds, trusted-source validation, or semantic fallback routing.
- Adding new public chat request fields.
- Adding cross-process circuit breaker state or persistent provider health storage.
- Introducing new MaaS providers beyond existing provider implementations.

## Decisions

- Use wrapper providers instead of spreading fallback logic through callers. A fallback wrapper per interface (`ModelProvider`, `JudgeEvaluationProvider`, `SearchProvider`, `ImageAnalysisProvider`) keeps assistant, tools, and evaluation code calling the same contracts while centralizing attempt ordering, timeout handling, classification of failures, retry policy, metrics, and diagnostics. The wrapper treats the first configured provider as the primary attempt for that role and treats later configured providers as fallback attempts; no provider implementation is inherently primary or inherently fallback.

- Configure chains per role with single-provider compatibility. New settings (`MODEL_PROVIDERS`, `JUDGE_PROVIDERS`, `SEARCH_PROVIDERS`, `VISION_PROVIDERS`) are parsed as ordered provider names. Gemini, OpenAI, mock, or any future provider can appear first or later in the chain and receives primary or fallback behavior from that position only. If a chain variable is absent, the factory builds a one-provider chain from the existing role setting (`MODEL_PROVIDER`, `JUDGE_PROVIDER`, `SEARCH_PROVIDER`, `VISION_PROVIDER`). `EMBEDDING_PROVIDER` remains single-provider only.

- Classify fallback eligibility by failure type, not semantic result. Timeouts, rate limits, service unavailable responses, network failures, empty provider responses, and invalid structured outputs are technical failures eligible for fallback. Valid semantic outputs, including answerability `insufficient`, are returned to the caller and never trigger fallback.

- Retry structured operations once before changing providers. `generate_json` and `judge_response` may fail due to malformed or invalid structured output. The wrapper retries the same provider once with the existing stricter/repair path where available, then moves to the next provider if output remains technically invalid. Plain text generation, vision, and search use the normal provider call once per provider attempt unless existing provider-level retry behavior already applies.

- Treat unusable search output as technical failure at the search-provider contract boundary. A search provider that returns no usable normalized results, only invalid URLs, or only internal Gemini redirect/grounding URLs has failed to satisfy `SearchProvider` for fallback use. The wrapper can then try the next search provider without changing downstream trusted-source validation.

- Use an in-memory circuit breaker. The breaker stores opened-until timestamps by `(role, provider_name, operation)` and opens only for transient, rate-limit, or timeout failures. It does not open for non-transient configuration errors or semantic insufficient results. Default open duration is 60 seconds and is configurable per role.

- Handle provider construction failures differently by environment. Local/development environments fail clearly when a configured provider in a chain has non-transient configuration errors, because hidden setup mistakes slow development. Production logs the configuration failure, marks that provider unavailable for the request, and continues through the rest of the chain so one bad fallback entry does not take down an otherwise available role.

- Store provider fallback metadata separately from semantic fallback metadata. Assistant message metadata gains `provider_fallbacks` for technical provider attempts, skipped providers, final provider, and success/failure status. Existing semantic fallback fields such as RAG insufficiency or `web_search_used` remain unchanged.

## Risks / Trade-offs

- Higher cost during outages -> Fallback calls may invoke later configured providers only after earlier configured providers fail; metrics make this visible.
- Increased latency when the first provider is unhealthy -> Per-attempt timeouts and circuit breaking bound repeated latency spikes.
- Provider output differences -> Existing internal provider interfaces and evidence validation remain the contract; semantic validation still decides answer quality.
- Hidden production misconfiguration -> Production continues past configuration errors for availability, but logs and metrics must clearly identify the bad provider and role.
- In-memory circuit breaker is per process -> Multi-worker deployments may each learn provider health independently; this is acceptable for the initial implementation and avoids external state.
- Search fallback could broaden evidence sources -> Downstream trusted-domain and source validation continue to decide which results are usable.
