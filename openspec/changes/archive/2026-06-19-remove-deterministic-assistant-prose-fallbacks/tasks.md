## 1. Provider Failure Metadata

- [x] 1.1 Add or extend sanitized typed provider failure metadata fields for provider, role, operation, category, transient flag, retryable flag, status code, attempt index and sanitized cause type.
- [x] 1.2 Update provider exception wrapping so original typed failure metadata is preserved through fallback wrapper errors.
- [x] 1.3 Fix provider failure classification to classify wrapped Gemini `503 UNAVAILABLE` as transient `service_unavailable`.
- [x] 1.4 Verify wrapped rate-limit, timeout, network and service-unavailable failures remain eligible for provider fallback and circuit breaker behavior.

## 2. Assistant Generation Contract

- [x] 2.1 Locate every assistant path that assigns deterministic fallback prose to user-facing `AssistantMessage.content`, including emergency Spanish responses, RAG fallback prose, action confirmations and tool-failure explanations.
- [x] 2.2 Replace deterministic fallback answer strings with structured model-generation payloads containing allowed facts, required points, prohibited points, evidence, limitations, source support, intent and `answer_language` as applicable.
- [x] 2.3 Ensure structured fallback drafts are never returned directly and are consumed only by configured model-generation paths.
- [x] 2.4 Add one gated model-based recovery attempt for recoverable empty, invalid or prompt-specific generation output failures.
- [x] 2.5 Ensure provider-wide unavailability, exhausted provider chains, timeouts, rate limits and service-unavailable failures bypass recovery prose and surface a retryable technical failure.
- [x] 2.6 Generate action confirmations, missing-data prompts and tool-failure explanations from structured action or failure facts through the model provider.

## 3. Chat API And Persistence

- [x] 3.1 Add a retryable machine-readable `/assistant/chat` error response for total model-generation failure with sanitized technical metadata.
- [x] 3.2 Preserve the user message when total generation failure occurs after user-message persistence begins.
- [x] 3.3 Prevent assistant-message persistence when no model-generated assistant content exists.
- [x] 3.4 Ensure API responses for total generation failure contain no synthetic assistant prose and no raw evidence fallback content.

## 4. Frontend Error Handling

- [x] 4.1 Update assistant chat frontend error handling to recognize retryable machine-readable assistant failures.
- [x] 4.2 Surface retryable assistant failures as request error or retry state without appending an assistant message bubble.
- [x] 4.3 Ensure local thread state remains consistent with backend persistence after retryable assistant failure.

## 5. Backend Tests

- [x] 5.1 Add provider fallback tests proving wrapped Gemini `503 UNAVAILABLE` classifies as transient `service_unavailable` and triggers fallback or circuit breaker behavior.
- [x] 5.2 Add backend assistant tests proving `_minimal_spanish_emergency_response()` or equivalent deterministic prose is not returned when fallback rendering fails.
- [x] 5.3 Add backend assistant tests proving RAG fallback does not return prewritten prose or raw evidence as final assistant content.
- [x] 5.4 Add backend assistant tests proving all-models-failed chat returns a retryable machine-readable error.
- [x] 5.5 Add backend persistence tests proving total generation failure persists the user message but does not persist an assistant message.
- [x] 5.6 Add backend tests proving recoverable empty or invalid generation output may perform one model-based recovery using structured facts and `answer_language`.
- [x] 5.7 Add backend tests proving action confirmations and tool-failure explanations are generated through the model path rather than hardcoded prose.
- [x] 5.8 Add regression coverage that non-English or paraphrased plant-care evidence still reaches semantic model/judge handling without deterministic keyword matching.

## 6. Verification

- [x] 6.1 Run the focused backend assistant and provider fallback test suites.
- [x] 6.2 Run focused frontend assistant chat tests or type checks covering retryable error handling.
- [x] 6.3 Search the assistant backend and frontend for remaining deterministic user-facing fallback prose and remove or convert any remaining occurrences.
- [x] 6.4 Run OpenSpec validation or status checks for `remove-deterministic-assistant-prose-fallbacks`.
