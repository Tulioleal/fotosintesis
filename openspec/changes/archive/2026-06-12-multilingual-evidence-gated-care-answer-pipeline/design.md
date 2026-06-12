## Context

The assistant already has LangGraph orchestration, RAG retrieval, structured lookup, trusted web fallback, source attribution, and separated plant display/binomial/scientific context. Existing requirements prefer `plant_binomial_name` for operations but still preserve legacy plant-only compatibility, and fallback web evidence can be persisted when selected for answers.

This change is narrower and stricter for assistant plant-care answers reached after identification confirmation. It adds a pre-retrieval classification and evidence validation contract so retrieval, fallback search, answer synthesis, and persistence are driven by canonical care aspects instead of broad topic matching. It also closes the remaining plant-name ambiguity for care answers: display names and nicknames remain user-facing context only and must not drive retrieval, search, structured lookup, or embeddings.

## Goals / Non-Goals

**Goals:**

- Classify multilingual assistant input into intent, topic, required care aspects, answer language, plant reference, retrieval need, and confidence before plant-care retrieval.
- Keep classification resilient with schema validation, configurable confidence thresholds, and deterministic fallback routing or clarification when the classifier is unusable.
- Use confirmed taxonomy only for care-answer retrieval/search/indexing, preferring `plant_binomial_name` and falling back only to `plant_scientific_name`.
- Validate local and web evidence against the requested required aspects before answer synthesis or persistence.
- Search the web only for missing required aspects after local evidence validation has run.
- Persist only validated relevant web evidence, including filterable `covered_aspects` and related metadata.
- Preserve the detected answer language and return complete, partial non-critical, safety-conservative, or no-evidence fallback responses.
- Expose bounded diagnostic metadata useful for clients and tests without exposing prompts, raw model reasoning, raw evidence bodies, or unexpected provider internals.

**Non-Goals:**

- Do not change plant identification, identification confirmation, garden/profile mutations, reminder execution, light measurement actions, or general out-of-domain handling beyond intent routing.
- Do not allow the classifier to resolve, mutate, or override plant identity.
- Do not persist unvalidated web evidence for future retrieval.
- Do not fabricate care advice to fill missing required aspects.
- Do not require the frontend to perform classification or evidence validation.

## Decisions

1. Add an LLM-first classifier before care-answer retrieval.

   Rationale: Multilingual and multi-topic questions need semantic classification into canonical aspects before retrieval can be precise. A cheaper/faster configured model from the same provider family keeps latency and cost lower while preserving provider behavior compatibility.

   Alternative considered: Extend deterministic keyword routing only. That is simpler but brittle across Spanish, Italian, and mixed-language phrasing and does not scale well to multi-aspect questions.

2. Validate classifier output with a closed schema and thresholds before using it.

   Rationale: The graph should treat classifier output as untrusted structured input. Invalid JSON, unknown enum values, timeout, provider failure, or confidence below the default `0.70` threshold routes to deterministic classification or clarification instead of contaminating retrieval and answer behavior.

   Alternative considered: Ask the main answer model to classify and answer in one pass. That makes routing less observable and prevents targeted evidence acquisition before synthesis.

3. Treat confirmed taxonomy as a hard gate for plant-care evidence operations.

   Rationale: Plant chat is reached after identification confirmation, so care answers can require `plant_binomial_name` or `plant_scientific_name` and log an inconsistent state if neither exists. Nicknames and display labels remain useful in the final answer but are unsafe for retrieval/search/indexing because they can be ambiguous or localized.

   Alternative considered: Preserve legacy fallback to `plant` for care-answer operations. Existing specs support legacy plant-only behavior broadly, but this stricter care-answer pipeline needs confirmed taxonomy to avoid embedding and retrieval pollution.

4. Validate evidence coverage with hybrid semantic validation and deterministic guardrails.

   Rationale: Semantic validation is needed to determine whether evidence actually answers an aspect, while deterministic rules enforce closed aspect subsets, threshold checks, direct evidence for safety-sensitive aspects, and missing-aspect handling. Defaults are `0.75` for evidence validation and `0.85` for safety-sensitive validation.

   Alternative considered: Use retrieval scores or chunk counts as sufficiency. High vector similarity or enough chunks does not prove that watering frequency, light exposure, toxicity, or treatment action is directly covered.

5. Use sequential targeted web fallback for missing aspects only.

   Rationale: Running web search only after local validation avoids unnecessary live calls and makes multi-aspect answers composable: RAG-covered aspects remain local, and web search targets only the missing canonical aspects with confirmed taxonomy.

   Alternative considered: Always search all requested aspects. That wastes provider calls, risks conflicting duplicate evidence, and can mask good local evidence.

6. Persist only validated web evidence with aspect metadata.

   Rationale: Persisted knowledge should be reusable by future aspect-filtered retrieval. Metadata must include topic, required aspects, covered aspects, language, evidence type, validation confidence, source domain, review status, and confirmed taxonomy where supported by the existing model.

   Alternative considered: Persist all selected web fallback evidence and rely on later retrieval scoring. That reintroduces unvalidated or off-aspect material into embeddings.

7. Keep answer synthesis evidence-limited and language-preserving.

   Rationale: The final answer may only include claims supported by validated evidence. Complete coverage produces a direct answer; partial non-critical coverage produces a bounded answer plus a brief limitation; no coverage produces a clear fallback; safety-sensitive missing primary aspects produce conservative refusal/fallback.

   Alternative considered: Let the answer model add general care tips from prior knowledge. That violates the evidence-gated contract and increases unsupported-claim risk.

8. Expose bounded diagnostics in assistant response metadata.

   Rationale: Clients, tests, and observability need to know intent, topic, requested/covered/missing aspects, evidence path, and answer language. Prompts, raw model reasoning, raw full evidence text, and internal provider errors should remain hidden except through existing tool failure metadata.

   Alternative considered: Expose full validation reports. That can leak prompt strategy, raw evidence, or provider-specific errors and is unnecessary for user-facing behavior.

## Risks / Trade-offs

- Classifier latency and cost increase per care-answer request -> Use a cheaper/faster configured model, strict timeout handling, and deterministic fallback.
- Classifier or validator may misclassify uncommon phrasing -> Preserve deterministic fallback, log bounded diagnostics, and cover canonical multilingual examples in tests.
- Strict taxonomy gating may block legacy plant-only care chats -> Limit the hard gate to this care-answer pipeline and return clarification plus inconsistent-state logging when taxonomy is unexpectedly missing.
- Web evidence validation adds another model-dependent step -> Use deterministic guardrails and thresholds so low-confidence validation cannot authorize unsupported claims or persistence.
- Partial answers can feel incomplete -> Keep limitation wording brief and only allow partial answers for non-critical care aspects with at least one validated aspect.
- Aspect metadata may require schema or indexing changes -> Prefer existing JSON metadata if already filterable; otherwise add a minimal migration for filterable `covered_aspects` support.

## Migration Plan

- Add configuration defaults for classifier model, classifier timeout, classification threshold, evidence validation threshold, and safety-sensitive validation threshold.
- Extend assistant response metadata shape in a backward-compatible way by adding bounded diagnostic keys under existing metadata structures.
- If existing knowledge metadata cannot filter by `covered_aspects`, add a minimal database/index migration to store covered aspects as filterable metadata for knowledge documents/chunks/embeddings.
- Deploy classifier and validation logic behind the care-answer path only; non-care intents continue through existing routing.
- Roll back by disabling the new care-answer pipeline path and returning to existing assistant retrieval/fallback behavior. Any persisted validated web evidence remains safe because it is still reviewed as `auto_ingested` validated web evidence.

## Open Questions

- None.
