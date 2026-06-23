## Context

The assistant already uses model/schema/judge-based routing, retrieval validation, and grounded answer generation for multilingual plant-care responses. Some failure and action paths still produce final user-facing text from deterministic strings, including an emergency Spanish response and fallback answer prose assembled from evidence. Those paths can surface content in the wrong language, expose raw evidence, or imply source-backed claims without model synthesis.

The provider fallback layer supports role-specific provider chains, transient failure classification, and circuit breaker behavior. The observed failure mode shows wrapped Gemini `503 UNAVAILABLE` errors can lose their original typed category and be treated as unknown or non-transient, preventing fallback and pushing the assistant toward degraded response generation.

## Goals / Non-Goals

**Goals:**

- Ensure every successful `AssistantMessage.content` from the assistant is model-generated from structured facts, action facts, or grounded evidence.
- Keep deterministic logic limited to routing, validation, provider selection, persistence boundaries, and retryable error shaping.
- Replace deterministic fallback prose with structured model inputs and a retryable API error when no model-generated response can be produced.
- Preserve the user message but avoid persisting synthetic assistant messages on total generation failure.
- Fix wrapped transient provider error classification and expose sanitized typed failure metadata for operational diagnostics.
- Update frontend chat handling so retryable assistant failures are shown as request errors without appending an assistant message.

**Non-Goals:**

- Do not add deterministic translated fallback strings or language-specific emergency messages.
- Do not add keyword lists, translated word lists, regex language detection, or semantic token matching.
- Do not change answerability judging semantics or evidence coverage thresholds.
- Do not broaden static UI chrome internationalization.
- Do not weaken source-grounding requirements or return raw evidence directly to users.

## Decisions

1. Treat model generation as the only producer of successful user-facing assistant prose.

   Deterministic code may still build typed response intents, choose recovery routing, validate schemas, and shape API errors, but it must not assign final prose to `AssistantMessage.content`. This preserves multilingual behavior and source-grounded synthesis. The alternative was to add translated fallback templates per language, but that would reintroduce deterministic language and semantic behavior that the assistant contract explicitly avoids.

2. Convert fallback prose into structured generation payloads.

   Existing fallback drafts should become model inputs containing allowed facts, required points, prohibited points, evidence summaries, source support, limitations, intent, and `answer_language`. The payload is acceptable only if it is consumed by a model provider and never returned directly. The alternative was to keep prewritten prose after redaction, but redaction does not solve language, grounding, or unsupported-claim risks.

3. Allow one model-based recovery only for recoverable generation failures.

   Empty output, invalid output, or prompt-specific formatting failures may use one recovery attempt with the same structured facts and `answer_language`. Provider-wide unavailability, exhausted provider chains, timeouts across all providers, and service-unavailable failures should surface as retryable technical API failures. This avoids loops while preserving a narrow safe recovery path. The alternative was unlimited retries, which increases latency and can hide provider incidents.

4. Return retryable machine-readable errors on total assistant generation failure.

   `/assistant/chat` should persist the user message, skip assistant-message persistence, and return an error payload with a retryable flag and sanitized technical category. This makes failure explicit to clients and avoids pretending a synthetic assistant response exists. The alternative was returning an empty assistant message, but that still breaks the conversation contract and complicates persistence semantics.

5. Preserve original provider failure metadata through wrappers.

   Provider fallback classification should inspect typed/original error metadata before wrapper text. Wrappers should carry sanitized fields such as provider, role, operation, category, transient flag, retryable flag, status code, and attempt metadata. This lets Gemini `503`, rate-limit, timeout, network, and service-unavailable failures drive fallback and circuit breaker behavior correctly. The alternative was string parsing wrapper messages, which is brittle and can misclassify provider-specific exceptions.

6. Keep frontend retryable failures out of the message thread.

   The frontend should surface retryable assistant failures as request errors or retry affordances without adding an assistant bubble. This matches backend persistence and prevents local UI state from diverging from stored conversation history. The alternative was appending a local fallback assistant message, which would recreate deterministic user-facing prose on the client.

## Risks / Trade-offs

- Breaking API behavior for clients that expect every chat request to return an assistant message -> document the retryable error contract and update the first-party frontend in the same change.
- More visible provider outages to users -> classify failures accurately, preserve provider fallback, and return retryable errors only after all safe generation paths fail.
- Recovery path could accidentally be used for provider outages -> gate recovery on typed failure categories and provider availability metadata.
- Tests may rely on deterministic fallback strings -> replace those assertions with contracts for model-generated content, retryable errors, and persistence boundaries.
- Sanitized metadata may omit details useful for debugging -> retain typed categories, status codes, provider role, operation, and attempt counts while excluding prompts, raw provider payloads, credentials, and raw evidence.
