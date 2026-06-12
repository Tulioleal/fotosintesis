## 1. Fallback Response Contract

- [x] 1.1 Add an internal structured fallback response draft type with intent, answer language, allowed facts, required points, prohibited points and rendering constraints.
- [x] 1.2 Add a minimal Spanish emergency response helper that never includes links and does not include unsupported botanical recommendations.
- [x] 1.3 Add a centralized fallback prompt builder that instructs the model to verbalize only the supplied draft in plain text.

## 2. Centralized Fallback Renderer

- [x] 2.1 Implement a centralized fallback-response generation method in the assistant graph using the existing text model provider.
- [x] 2.2 Ensure fallback rendering failures or empty outputs return the minimal Spanish emergency response.
- [x] 2.3 Ensure fallback rendering failures are recorded as non-blocking tool failure metadata when available.
- [x] 2.4 Ensure fallback prompts prohibit links, unsupported facts, unsupported recommendations and prominent internal fallback reason codes unless explicitly supplied as allowed user-facing facts.

## 3. Classifier Language Handling

- [x] 3.1 Remove deterministic language detection from assistant graph code.
- [x] 3.2 Update deterministic classification to default both `language` and `answer_language` to `es` while preserving deterministic intent, topic and required-aspect routing.
- [x] 3.3 Update the LLM classifier prompt to derive `answer_language` from the actual language used by the user message.
- [x] 3.4 Update the LLM classifier prompt to ignore instructions that request a different response language than the message language.

## 4. Fallback Path Conversion

- [x] 4.1 Convert missing confirmed taxonomy responses to structured fallback drafts rendered by the centralized fallback renderer.
- [x] 4.2 Convert unsafe, out-of-domain, missing plant context and ambiguous plant clarification responses to structured fallback drafts.
- [x] 4.3 Convert missing reminder data, reminder action failure and light-measurement fallback responses to structured fallback drafts.
- [x] 4.4 Convert insufficient-evidence, partial-evidence and degraded-evidence fallback responses to structured fallback drafts.
- [x] 4.5 Convert conservative pet-safety and human-edibility fallbacks to policy-driven structured fallback drafts with required safety points and prohibited claims.
- [x] 4.6 Convert grounded model-generation failure handling to use a structured model-generation-failed fallback draft before using the minimal Spanish emergency response.
- [x] 4.7 Preserve existing source metadata, fallback reason metadata and deterministic routing decisions while converting user-facing text generation.

## 5. Tests

- [x] 5.1 Add tests that successful classifier output controls `answer_language` for fallback rendering.
- [x] 5.2 Add tests that Spanish messages requesting English responses still use Spanish when the classifier follows the prompt contract.
- [x] 5.3 Add tests that English messages requesting Spanish responses still use English when the classifier follows the prompt contract.
- [x] 5.4 Add tests that classifier failure, timeout, invalid output, forbidden extra fields and low confidence default language fields to Spanish.
- [x] 5.5 Add tests that fallback renderer failure returns the minimal Spanish emergency response with no links.
- [x] 5.6 Add tests that conservative pet-safety and human-edibility fallbacks preserve required safety points and avoid unsupported safety claims.
- [x] 5.7 Add tests that converted clarification, action failure and missing taxonomy paths call the fallback renderer rather than returning rich hardcoded prose directly.
- [x] 5.8 Update existing model-failure tests to reflect centralized fallback rendering and Spanish emergency behavior when rendering also fails.

## 6. Verification

- [x] 6.1 Run the assistant agent test suite and fix regressions.
- [x] 6.2 Run the relevant backend tests for assistant, knowledge fallback and provider mocks.
- [x] 6.3 Review assistant graph user-facing `answer` assignments to confirm fallback paths use the centralized renderer or minimal Spanish emergency response.
