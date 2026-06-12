## 1. Source-Level Web Validation

- [x] 1.1 Add an internal representation for a validated web source that carries the original `TrustedPageEvidence`, source-specific `covered_aspects`, `missing_aspects` and validation confidence.
- [x] 1.2 Replace aggregate `_validate_web_evidence` behavior with per-source validation over the top three usable fallback results.
- [x] 1.3 Run per-source validation concurrently while preserving the existing semantic judge, deterministic aspect guardrails and configured standard/safety thresholds.
- [x] 1.4 Ensure each validation is scoped only to the currently requested missing aspects and cannot return covered aspects outside that set.

## 2. Fallback Graph Filtering

- [x] 2.1 Update `fallback_web_search` so only independently validated sources are written to `web_results` and response `sources`.
- [x] 2.2 Compute final `covered_aspects` as the union of prior validated RAG or structured aspects and all independently validated web-source aspects.
- [x] 2.3 Compute `missing_aspects` from requested fallback aspects not covered by any validated source.
- [x] 2.4 Compute overall `web_validation_confidence` as the minimum confidence across included validated web sources.
- [x] 2.5 Preserve existing partial-answer and conservative safety fallback routing when web validation covers only some aspects or no safety-sensitive aspect.

## 3. Source-Level Persistence

- [x] 3.1 Update the web evidence ingestion handoff so unvalidated and off-aspect sources are never passed to persistence.
- [x] 3.2 Persist each independently validated source as a separate knowledge document rather than one merged document.
- [x] 3.3 Store source-specific `covered_aspects`, validation confidence, evidence type, review status, language, topic and source domain in each document metadata payload.
- [x] 3.4 Ensure each persisted source is independently chunked, embedded and indexed through the existing `KnowledgeVectorIndex` path.
- [x] 3.5 Keep ingestion failures best-effort and non-blocking for already generated fallback answers.

## 4. Regression Coverage

- [x] 4.1 Add a graph-level regression test where web fallback returns Source A for the requested watering aspect and Source B as a trusted off-aspect result.
- [x] 4.2 Assert Source A appears in the answer prompt and assistant response sources.
- [x] 4.3 Assert Source B does not appear in the answer prompt or assistant response sources.
- [x] 4.4 Assert Source B is not passed to ingestion.
- [x] 4.5 Assert ingestion metadata includes only Source A's covered aspects and validation confidence.
- [x] 4.6 Add or update tests for multi-source source-specific persistence and safety-sensitive threshold behavior if not already covered by the graph regression.

## 5. Verification

- [x] 5.1 Run the relevant assistant agent and knowledge acquisition tests.
- [x] 5.2 Run the existing backend test subset that covers RAG fallback, source metadata and ingestion behavior.
- [x] 5.3 Confirm existing assistant and RAG tests continue passing without public API changes.
