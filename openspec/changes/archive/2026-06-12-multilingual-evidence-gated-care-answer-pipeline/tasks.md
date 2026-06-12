## 1. Configuration And Contracts

- [x] 1.1 Add configuration for classifier model selection, classifier timeout, classification acceptance threshold defaulting to `0.70`, evidence validation threshold defaulting to `0.75`, and safety-sensitive validation threshold defaulting to `0.85`.
- [x] 1.2 Define closed classifier types for allowed intents, topics, required aspects, classifier result fields, confidence, and retrieval need.
- [x] 1.3 Define evidence validation types for answerability, covered aspects, missing aspects, unsupported-claim risk, reason, and confidence.
- [x] 1.4 Define safety-sensitive aspects, including pet toxicity and human edibility, so validation and answer synthesis can apply the higher threshold.
- [x] 1.5 Extend assistant response metadata types to include bounded diagnostic fields for intent, topic, required aspects, covered aspects, missing aspects, evidence path, and answer language.

## 2. Multilingual Classification And Routing

- [x] 2.1 Implement the LLM-based multilingual classifier using the configured cheaper/faster model from the main provider family.
- [x] 2.2 Add strict schema validation for classifier JSON and reject unknown intent, topic, or required-aspect values.
- [x] 2.3 Add timeout, provider failure, invalid JSON, and low-confidence handling that falls back to deterministic routing or clarification.
- [x] 2.4 Implement deterministic fallback routing for common care questions, non-care intents, and unclear input.
- [x] 2.5 Route non-care classifier intents away from the plant-care evidence pipeline while preserving existing reminder, light, garden, identification, unsafe, and out-of-domain behavior.

## 3. Confirmed Taxonomy Gate

- [x] 3.1 Add a care-answer operational taxonomy resolver that prefers `plant_binomial_name` and falls back only to `plant_scientific_name`.
- [x] 3.2 Prevent nickname, apodo, display `plant`, and classifier `plant_reference` values from being used in care-answer retrieval, structured lookup, web search, embeddings, or indexing.
- [x] 3.3 Preserve the display plant name for user-facing answer context when confirmed taxonomy is used for evidence operations.
- [x] 3.4 Return clarification or inconsistent-state fallback and log the inconsistent missing-taxonomy state when care-answer retrieval is requested without confirmed taxonomy.

## 4. Aspect-Aware Evidence Validation

- [x] 4.1 Implement local RAG evidence validation against requested `required_aspects` using LLM semantic validation plus deterministic guardrails.
- [x] 4.2 Enforce that validation `covered_aspects` is always a subset of requested `required_aspects`.
- [x] 4.3 Treat evidence as not fully answerable whenever any requested aspect remains missing.
- [x] 4.4 Treat evidence below the configured validation threshold as not answerable for requested aspects.
- [x] 4.5 Require direct evidence and the configured safety-sensitive threshold for safety-sensitive aspects.
- [x] 4.6 Ensure generic plant-care evidence does not validate as covering specific aspects such as watering frequency without direct support.

## 5. Targeted Web Fallback And Validation

- [x] 5.1 Trigger trusted web fallback only after local evidence validation fails to cover all requested required aspects.
- [x] 5.2 Build web search requests for all requested aspects when RAG covers none and only missing aspects when RAG covers some.
- [x] 5.3 Construct web search queries from confirmed taxonomy plus missing canonical aspects, excluding display names and nicknames.
- [x] 5.4 Validate web evidence against the same requested missing aspects before using it for answers or persistence.
- [x] 5.5 Combine validated RAG-covered aspects and validated web-covered aspects into one final coverage set and evidence path.

## 6. Validated Web Evidence Persistence

- [x] 6.1 Update web evidence ingestion metadata to include topic, required aspects, covered aspects, language, evidence type `validated_web`, validation confidence, source domain when available, review status `auto_ingested`, and confirmed taxonomy.
- [x] 6.2 Persist, chunk, embed, and index only web evidence that validates above threshold for at least one requested aspect.
- [x] 6.3 Ensure unvalidated, low-confidence, or off-aspect web evidence is not persisted, chunked, embedded, or indexed.
- [x] 6.4 Add or adjust metadata filtering/indexing support so future retrieval can filter by confirmed taxonomy, topic, covered aspects, review status, evidence type, and source domain when available.
- [x] 6.5 Keep validated web evidence persistence failures non-blocking and continue recording failures through existing tool failure metadata.

## 7. Answer Synthesis And Diagnostics

- [x] 7.1 Update plant-care answer synthesis prompts or deterministic fallback summaries so final claims are limited to validated evidence only.
- [x] 7.2 Preserve the classifier `answer_language` for complete, partial, and fallback care answers.
- [x] 7.3 Return direct grounded answers when all requested aspects are validated.
- [x] 7.4 Return partial non-critical answers only for validated covered aspects and briefly state missing unvalidated aspects.
- [x] 7.5 Return a no-evidence fallback without fabricated advice when no requested aspects validate.
- [x] 7.6 Return conservative safety fallback when primary safety-sensitive evidence is missing or below the safety threshold.
- [x] 7.7 Include bounded diagnostic metadata in assistant responses and exclude prompts, raw model reasoning, raw full evidence text, and provider internals beyond existing tool failures.

## 8. Tests

- [x] 8.1 Add a test that a Spanish watering frequency question routes to `watering_frequency_or_trigger` and preserves Spanish answer language.
- [x] 8.2 Add a test that an Italian watering frequency question routes to `watering_frequency_or_trigger` and preserves Italian answer language.
- [x] 8.3 Add a test that nickname or display plant name is preserved in the answer but not used for retrieval, search, structured lookup, embeddings, or indexing.
- [x] 8.4 Add tests that retrieval uses `plant_binomial_name` and falls back only to `plant_scientific_name`.
- [x] 8.5 Add a test that generic RAG evidence about plant care fails validation for watering frequency.
- [x] 8.6 Add a test that web search is called only for missing aspects after RAG validation.
- [x] 8.7 Add a test that a multi-aspect question can combine RAG-covered and web-covered evidence.
- [x] 8.8 Add a test that a partial non-critical answer is returned when only some requested aspects are validated.
- [x] 8.9 Add a test that a safety-sensitive answer refuses unsafe partial advice without direct validated evidence.
- [x] 8.10 Add a test that validated web evidence is persisted with `covered_aspects` and related validated web metadata.
- [x] 8.11 Add a test that diagnostic metadata includes intent, topic, required aspects, covered aspects, missing aspects, evidence path, and language.
- [x] 8.12 Add tests that classifier failure, invalid output, timeout, and low confidence fall back to deterministic routing or clarification.
- [x] 8.13 Run the relevant backend assistant, RAG acquisition, and metadata persistence tests and fix regressions.
