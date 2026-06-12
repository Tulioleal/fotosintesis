## 1. Answerability Evaluation

- [x] 1.1 Add an internal answerability result structure with `answerable`, `missing_aspects`, `reason` and `confidence` fields.
- [x] 1.2 Add a strict answerability rubric for judging whether supplied evidence directly answers the user's exact question.
- [x] 1.3 Implement a helper that evaluates RAG chunks through `providers.judge.judge_response()`.
- [x] 1.4 Implement a helper that evaluates structured plant-data evidence through `providers.judge.judge_response()`.
- [x] 1.5 Normalize malformed or partial judge outputs defensively so uncertain answers are treated as not directly answerable.

## 2. Assistant Graph Routing

- [x] 2.1 Replace confidence-only RAG sufficiency with answerability-confirmed sufficiency.
- [x] 2.2 Ensure empty RAG chunks remain insufficient without calling the judge.
- [x] 2.3 Record `rag_not_answerable` when RAG chunks exist but fail strict answerability.
- [x] 2.4 Preserve structured plant-data lookup after non-answerable RAG evidence.
- [x] 2.5 Evaluate structured plant-data answerability before generating structured answers.
- [x] 2.6 Record `structured_not_answerable` when structured evidence exists but does not directly answer.
- [x] 2.7 Continue to trusted web search when RAG and structured evidence are missing or not directly answerable.
- [x] 2.8 Record `web_search_used` when trusted web search is invoked after local evidence is not answerable.

## 3. Conservative Safety Fallback

- [x] 3.1 Add safety-topic detection for pet safety, edibility, toxicity and consumption questions.
- [x] 3.2 Add conservative fallback text for edibility and consumption questions when no direct evidence is available.
- [x] 3.3 Add conservative fallback text for pet safety and toxicity questions when no direct evidence is available.
- [x] 3.4 Record `conservative_safety_fallback` when conservative safety fallback is used.
- [x] 3.5 Preserve existing degraded limitation behavior for non-safety topics with no direct evidence.

## 4. Internal Metadata And Observability

- [x] 4.1 Add internal fallback reason tracking to assistant state or response metadata without making reason codes prominent in final answer text.
- [x] 4.2 Add structured logs for RAG answerability decisions with evidence type, answerable boolean, missing aspects and trace correlation.
- [x] 4.3 Add structured logs for structured evidence answerability decisions.
- [x] 4.4 Add structured logs for fallback routing to trusted web search.
- [x] 4.5 Ensure logs do not include secrets, API keys or excessive raw evidence content.

## 5. Tests

- [x] 5.1 Add test proving a general care RAG chunk is not sufficient for a pet safety question.
- [x] 5.2 Add test proving a general care RAG chunk is not sufficient for a native range question.
- [x] 5.3 Add test proving a RAG chunk directly mentioning pet safety is sufficient and does not trigger web search.
- [x] 5.4 Add test proving structured lookup runs after non-answerable RAG evidence.
- [x] 5.5 Add test proving generic structured evidence does not block trusted web search.
- [x] 5.6 Add test proving trusted web search is called when RAG and structured evidence are not directly answerable.
- [x] 5.7 Add test proving conservative safety fallback is used when pet safety evidence is unavailable across all sources.
- [x] 5.8 Add test proving conservative safety fallback is used when edibility evidence is unavailable across all sources.
- [x] 5.9 Add test proving internal fallback reasons are recorded.
- [x] 5.10 Add test proving existing sufficient RAG answer path still works.
- [x] 5.11 Add observability test proving answerability/fallback decision logs are emitted or log helper is called.

## 6. Verification

- [x] 6.1 Run assistant agent tests affected by answerability and fallback routing from `backend/`.
- [x] 6.2 Run provider/system tests from `backend/` to ensure judge provider wiring remains valid.
- [x] 6.3 Run knowledge/RAG tests from `backend/` to ensure existing acquisition behavior remains compatible.
- [x] 6.4 Manually verify or document expected runtime logs for questions like `es segura para mascotas?` showing answerability rejection and a search provider call.
