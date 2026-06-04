## 1. Assistant Tooling

- [x] 1.1 Add an assistant tool method for best-effort fallback web evidence ingestion using `KnowledgeDocumentInput`, `KnowledgeSourceInput`, `KnowledgeVectorIndex.ingest_document(...)`, and the configured embedding provider.
- [x] 1.2 Ensure fallback ingestion failures return `ToolResult(ok=False, ...)` without raising into the assistant graph.

## 2. Graph State And Routing

- [x] 2.1 Add `web_results` to `AssistantState` and source mapping helpers for provider `SearchResult` objects.
- [x] 2.2 Add a `fallback_web_search` graph node that runs after insufficient RAG sufficiency evaluation.
- [x] 2.3 Route insufficient RAG evidence to `fallback_web_search`, then to answer generation when web results exist or to existing clarify/limitation handling when they do not.
- [x] 2.4 Update the sequential graph fallback path to match the LangGraph routing behavior.

## 3. Answer Generation And Persistence

- [x] 3.1 Update `generate_answer` to prefer sufficient RAG chunks and use web-search snippets only when no sufficient chunks are available.
- [x] 3.2 Include language that fallback answers are based on live web evidence and are not reviewed persisted knowledge.
- [x] 3.3 Add web-search result sources to assistant response metadata.
- [x] 3.4 Trigger best-effort fallback evidence ingestion after generating a web-evidence answer and record persistence failures in `tool_failures` without blocking the answer.

## 4. Tests

- [x] 4.1 Update the degraded-knowledge assistant test so degraded RAG triggers `trusted_web_search` before limitation-only output.
- [x] 4.2 Add a test where degraded RAG plus web results produces a web-evidence answer and includes web sources.
- [x] 4.3 Add a test where degraded RAG plus empty or failed web search preserves the old limitation/manual-search response.
- [x] 4.4 Add a test proving fallback web evidence ingestion is called when web results are used, and that ingestion failure does not block the answer.

## 5. Verification

- [x] 5.1 Run the focused assistant tests for the fallback flow.
- [x] 5.2 Run the relevant knowledge RAG tests if fallback ingestion touches knowledge ingestion helpers.
