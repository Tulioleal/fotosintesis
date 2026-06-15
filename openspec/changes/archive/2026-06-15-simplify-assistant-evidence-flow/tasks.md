## 1. Contracts And Topic Mapping

- [x] 1.1 Extend assistant care answerability contracts with `status`, `covered_aspects`, `missing_aspects`, `source_support`, `contradictions`, `reason`, and `confidence` while preserving `answerable` compatibility.
- [x] 1.2 Add structural validation for answerability results so incoherent `full`, `partial`, `insufficient`, or `contradictory` outputs degrade safely.
- [x] 1.3 Add `CareTopic.taxonomy` and map `RequiredAspect.native_range` to the taxonomy topic.
- [x] 1.4 Update classifier and fallback parsing tests for explicit answerability status and taxonomy topic mapping.

## 2. Enriched RAG Retrieval

- [x] 2.1 Implement enriched RAG query construction from confirmed taxonomy, topic, required aspects, and original user question.
- [x] 2.2 Keep existing metadata filters for taxonomy/topic where applicable while ensuring the semantic query no longer relies only on topic.
- [x] 2.3 Update RAG retrieval tests to assert the enriched query contains required aspects and user question terms.
- [x] 2.4 Verify RAG full evidence returns without web search or structured plant-data lookup.

## 3. Graph Routing Simplification

- [x] 3.1 Remove or bypass `fallback_plant_data` routing from the normal assistant plant-care chat graph.
- [x] 3.2 Ensure RAG statuses `partial`, `insufficient`, and `contradictory` route directly to trusted web search.
- [x] 3.3 Ensure RAG status `full` routes directly to answer generation without web search.
- [x] 3.4 Preserve existing clarification, non-care intent, action, and emergency model-failure routes.
- [x] 3.5 Update assistant graph tests to assert `plant_data_lookup` is not called in the normal chat-time plant-care answer path.

## 4. Final Combined Evidence Judge

- [x] 4.1 Replace per-source web answerability judging with one final combined judge over user question, taxonomy, topic, required aspects, RAG chunks, RAG judge result, web evidence, URLs, and metadata.
- [x] 4.2 Fetch at most three usable web sources from one web search call and degrade failed page fetches to snippets where allowed.
- [x] 4.3 Parse final judge output into the explicit answerability contract.
- [x] 4.4 Validate final judge `source_support` and `contradictions` structurally before answer synthesis or persistence.
- [x] 4.5 Update tests for full, partial, insufficient, and contradictory final judge outcomes.

## 5. Answer Synthesis Policy

- [x] 5.1 Update answer prompt construction to accept final answerability status, verified source-supported claims, missing aspects, contradictions, and allowed general guidance constraints.
- [x] 5.2 Ensure verified evidence and general guidance are separated in generated answers and not blended in the same sentence.
- [x] 5.3 Ensure partial answers state supported aspects and missing unverified aspects.
- [x] 5.4 Ensure insufficient answers may include conservative general guidance only when labeled as not source-validated for the specific plant/question.
- [x] 5.5 Ensure contradictory answers show source links for conflicting claims and avoid definitive recommendations.
- [x] 5.6 Preserve source metadata and bounded diagnostics without exposing prompts, raw reasoning, or full raw evidence.

## 6. Validated Claim Persistence

- [x] 6.1 Build small validated claim documents from final judge `source_support` with taxonomy, topic, covered aspects, claim, evidence quote, source URL, confidence, retrieval timestamp, and metadata.
- [x] 6.2 Persist only `full` and safe `partial` source-supported claims.
- [x] 6.3 Prevent persistence of insufficient evidence, contradictory evidence, general LLM guidance, unsupported claims, final assistant answer text, and full pages by default.
- [x] 6.4 Ensure existing metadata JSON stores `evidence_type: "validated_web_claim"`, `answerability_status`, `validation_confidence`, `source_support_claim`, `source_support_quote`, and `persisted_from: "assistant_final_judge"` without a migration.
- [x] 6.5 Update knowledge acquisition tests for claim-only persistence and non-persistence cases.

## 7. Background Ingestion Scheduling

- [x] 7.1 Move assistant fallback evidence ingestion scheduling out of graph execution and into `AssistantService.chat` after response preparation.
- [x] 7.2 Pass only serializable validated claim payloads to the background ingestion task.
- [x] 7.3 Make the background ingestion task open its own `AsyncSessionLocal` session and never reuse the request session.
- [x] 7.4 Add commit, rollback, and explicit exception logging with conversation, plant, source, and answerability context.
- [x] 7.5 Update tests to verify chat response persistence does not depend on background ingestion success.

## 8. Structured Provider Scope

- [x] 8.1 Keep Trefle/Perenual providers and `plant_data_lookup` services available outside the normal chat-time path.
- [x] 8.2 Remove chat-time dependencies on structured provider latency, answerability, and ingestion.
- [x] 8.3 Update structured lookup tests to distinguish retained backend capability from skipped chat-time orchestration.

## 9. Regression And Acceptance Tests

- [x] 9.1 Add or update tests proving RAG full answers do not call web search.
- [x] 9.2 Add or update tests proving RAG partial, insufficient, and contradictory statuses call web search.
- [x] 9.3 Add or update tests proving one web search call can provide up to three fetched sources and one final combined judge call.
- [x] 9.4 Add or update tests proving deterministic keyword validation no longer blocks semantically valid judge-supported evidence.
- [x] 9.5 Add or update tests proving insufficient and contradictory outcomes are not persisted.
- [x] 9.6 Add or update tests proving full and safe partial outcomes persist only source-supported claims.
- [x] 9.7 Run the relevant backend assistant and knowledge RAG test suites.
