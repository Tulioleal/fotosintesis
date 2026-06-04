## 1. Prompt Attribution

- [x] 1.1 Update grounded answer prompt construction to add a conditional instruction for `structured_api` evidence requiring the final answer to mention structured provider sources used.
- [x] 1.2 Ensure the instruction uses existing provider/source metadata and does not change RAG or live web prompt behavior beyond shared formatting.
- [x] 1.3 Preserve deterministic fallback answers and source metadata response behavior.

## 2. Regression Tests

- [x] 2.1 Add or update assistant tests proving structured API prompts include an explicit provider-source mention requirement.
- [x] 2.2 Add or update assistant tests proving provider names remain present in structured API prompt context.
- [x] 2.3 Confirm RAG and live web synthesis tests continue to pass without requiring structured provider attribution.

## 3. Verification

- [x] 3.1 Run backend assistant tests.
- [x] 3.2 Run OpenSpec status or validation for `require-structured-provider-attribution`.
