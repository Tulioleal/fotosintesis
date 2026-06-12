## Context

The assistant currently retrieves RAG chunks, computes sufficiency with a simple confidence-oriented check, then generates an answer if enough chunks are present. That allows generic high-confidence care evidence for a plant to block fallback even when the user asks a different question, such as pet safety, edibility, native range, water temperature or morphology. In practice, the assistant can answer with "the available evidence does not include that" while never calling trusted web search.

The backend already has an independent judge provider role through `ProviderRegistry.judge`, and the assistant graph already has a sufficiency node, structured plant-data fallback, trusted web fallback and grounded answer generation. This change reuses those existing seams. It changes the definition of "sufficient" from "retrieved chunks exist and are high confidence" to "the judge says the supplied evidence directly answers the current user question."

The user-facing behavior should improve without exposing internal routing. The assistant should use better evidence when available, and for safety-sensitive topics it should remain conservative when direct evidence still cannot be found.

## Goals / Non-Goals

**Goals:**

- Evaluate RAG answerability with `providers.judge.judge_response()` when retrieved chunks are present.
- Make answerability strict: evidence must directly answer the user's exact question, not just be generally relevant to the plant.
- Preserve fallback order: RAG answerability check, structured lookup, structured answerability check, trusted web search, then final answer or conservative fallback.
- Ensure generic structured evidence does not block web search when it does not directly answer the question.
- Keep web fallback behavior compatible with the existing trusted-first search policy.
- Add conservative fallback language for pet safety, edibility, toxicity and consumption questions when direct evidence is unavailable.
- Track internal fallback reasons for debugging without making routing details prominent in the final user-facing answer.
- Add structured logs for answerability decisions and fallback routing decisions.
- Keep deterministic tests possible through mock/fake judge behavior.

**Non-Goals:**

- Do not add a new provider role.
- Do not replace the configured model provider for final answer generation.
- Do not use the runtime model provider for answerability when the judge provider is available.
- Do not perform web search before structured lookup in the default flow.
- Do not expose verbose internal routing details in final answer text.
- Do not add live external-provider tests to CI.
- Do not change the trusted-first search provider behavior from the Gemini search provider change.
- Do not add database schema changes for fallback reasons in this change.

## Decisions

1. Use the judge provider for strict answerability.

   The graph should call `providers.judge.judge_response()` with the user question, plant context, topic, evidence snippets, source metadata and a strict answerability rubric. The answerability result should be reduced to an internal structure with `answerable`, `missing_aspects`, `reason` and `confidence` fields.

   Alternative considered: use `providers.model.generate_json()`. That would couple answerability to the final generation provider and duplicate an existing judge role. The judge role is better aligned with evaluation tasks and can be mocked deterministically in tests.

2. Replace confidence-only sufficiency with answerability-confirmed sufficiency.

   No chunks remains insufficient. Chunks exist triggers judge answerability. RAG is sufficient only when the judge says the evidence directly answers the exact user question. A care chunk for `Chlorophytum comosum` is not sufficient for pet safety or native range unless it explicitly contains that information.

   Alternative considered: deterministic topic keyword matching. That is cheaper, but it is brittle and would require extensive botanical topic taxonomies. The judge can compare the actual question and evidence more flexibly.

3. Preserve existing fallback order.

   If RAG is not answerable, the graph should still try `plant_data_lookup` before `trusted_web_search`. This keeps structured plant-data providers useful for taxonomy/care facts and avoids unnecessary web search when structured evidence directly answers the question.

   Alternative considered: skip structured lookup and search web immediately. That would solve the observed issue faster but would abandon an existing source priority and likely increase search calls unnecessarily.

4. Evaluate structured evidence answerability too.

   Structured lookup returning any data is not enough. The graph should evaluate whether structured evidence directly answers the current question. If it does, answer from structured evidence. If it does not, record `structured_not_answerable` and continue to trusted web search.

   Alternative considered: let structured lookup block search when it returns anything. That is rejected because generic provider metadata can be just as non-answerable as generic RAG chunks.

5. Keep web evidence answer generation as the last evidence fallback.

   If trusted web search returns usable evidence, the assistant should answer from that evidence using the existing grounded generation path. This change does not require a second judge pass over web evidence before generating, but it should record `web_search_used`. If web search returns no usable selected evidence, the graph proceeds to conservative safety fallback for safety-sensitive questions or existing limitation handling for other questions.

   Alternative considered: judge web evidence answerability too. That would be more thorough, but it adds latency and cost after an already targeted search. It can be added later if web results prove noisy.

6. Add conservative safety fallback for safety-sensitive topics.

   When the user asks about pet safety, edibility, toxicity or consumption and no direct evidence source can answer, the assistant should state that direct evidence was not available and give conservative safety guidance. For edibility/consumption, recommend not consuming the plant. For pet safety/toxicity, recommend keeping the plant away from pets until verified and consulting a veterinarian or poison-control style source if ingestion occurs.

   Alternative considered: always return "insufficient evidence" without guidance. That is safer against hallucination but less useful for safety-sensitive questions where conservative behavior is appropriate.

7. Store fallback reasons internally.

   The graph should track structured reason strings such as `rag_not_answerable`, `structured_not_answerable`, `web_search_used`, `web_search_no_direct_answer` and `conservative_safety_fallback`. These can live in assistant state and response/tool metadata or failure-style debug metadata. The final answer should naturally mention evidence limitations, but not list internal routing codes.

   Alternative considered: expose routing reasons directly to users. That would make answers noisy and implementation-centric.

8. Log answerability decisions.

   The system should emit structured logs with trace correlation, evidence type, answerable boolean, missing aspects and fallback reason. This makes runtime behavior diagnosable from logs: operators should see when RAG was rejected and web search was used.

   Alternative considered: rely only on provider-call logs. Provider logs show model/search calls but not why the graph made routing decisions.

## Risks / Trade-offs

- Additional judge calls increase latency and provider cost. Mitigation: call judge only when evidence exists; skip judge for empty RAG and use deterministic mock/fake judge behavior in tests.
- Judge decisions may be inconsistent or too strict. Mitigation: use a compact explicit rubric, normalize malformed judge results defensively and add tests for strict examples.
- Mock judge behavior may need updates to avoid breaking existing tests. Mitigation: isolate answerability helpers and inject fake tool/provider behavior in assistant tests.
- More questions may reach web search, increasing search cost and latency. Mitigation: preserve structured lookup before web search and only search when evidence is judged not answerable.
- Conservative safety fallback could be perceived as an answer without evidence. Mitigation: explicitly state that direct evidence was unavailable and keep guidance conservative rather than factual about the specific plant.
- Internal fallback reasons may become confused with user-facing tool failures. Mitigation: keep reason codes separate from hard tool failures when possible and assert they are metadata/debug signals.

## Migration Plan

1. Add answerability result helpers and strict judge prompt/rubric.
2. Update the graph sufficiency node to call judge answerability for RAG chunks.
3. Update structured fallback handling to evaluate structured evidence answerability before generating a structured answer.
4. Update fallback routing to continue to trusted web search when RAG and structured evidence are not answerable.
5. Add conservative safety fallback for safety-sensitive topics with no direct answerable evidence.
6. Add fallback reason tracking and structured decision logs.
7. Add tests for answerability, fallback routing, conservative safety behavior and logs/metadata.

Rollback is code-only: restore the previous confidence-based sufficiency behavior and remove the additional answerability routing if judge latency/cost or strictness is unacceptable.

## Open Questions

None for product behavior. Implementation should decide the smallest internal representation for answerability results and fallback reasons based on existing assistant state and response metadata shape.
