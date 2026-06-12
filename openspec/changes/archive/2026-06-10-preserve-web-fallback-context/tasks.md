## 1. Trusted Web Fallback Query

- [x] 1.1 Update `fallback_web_search` in `backend/app/assistant/graph.py` to build the trusted web query from the operational scientific name, capped `state["message"]`, and `botanical trusted source` terms.
- [x] 1.2 Ensure the new query no longer depends on the reduced topic value for trusted web fallback searches.

## 2. Failure Metadata Preservation

- [x] 2.1 Update the trusted web search failure branch to return the already-computed `fallback_reasons` list along with `tool_failures`.
- [x] 2.2 Confirm the failure path still returns degraded limitation or manual-search guidance without inventing unsupported botanical facts.

## 3. Test Coverage

- [x] 3.1 Update the existing degraded-knowledge web query assertion to expect question-preserving query text.
- [x] 3.2 Add assertions that pet-safety and native-range unsupported botanical questions preserve `mascotas` and `nativa` in `tools.web_search_query`.
- [x] 3.3 Add an assertion that failed trusted web search preserves `web_search_used` in `result["fallback_reasons"]`.
- [x] 3.4 Run `pytest backend/tests/test_assistant_agent.py` and resolve any regressions.
