## 1. Configuration and Factory Wiring

- [x] 1.1 Add `openai_search_model` to backend settings with a default consistent with existing OpenAI role model settings.
- [x] 1.2 Add `OPENAI_SEARCH_MODEL` to `backend/.env.example` near the other OpenAI provider settings.
- [x] 1.3 Update provider factory search construction to accept settings and support `SEARCH_PROVIDER=openai`.
- [x] 1.4 Reuse role-specific OpenAI credential validation so missing credentials fail only when OpenAI search is selected.

## 2. OpenAI Search Provider

- [x] 2.1 Implement `OpenAISearchProvider` in `backend/app/providers/openai.py` using existing `_client`, `_logged`, async Responses API and provider naming patterns.
- [x] 2.2 Use the OpenAI Responses API web search tool for search requests and include `allowed_domains` as prompt guidance when supplied.
- [x] 2.3 Parse URL citation annotations into `SearchResult(title, url, snippet, source_domain)` values.
- [x] 2.4 Ignore invalid citations without usable URLs and keep the provider result shape deterministic for tests.

## 3. Integration Preservation

- [x] 3.1 Keep the public `SearchProvider` interface unchanged.
- [x] 3.2 Keep `KnowledgeAcquisitionService` search invocation unchanged.
- [x] 3.3 Preserve `TrustedSourceValidator` as the authoritative filter for HTTPS and approved domains after search results are returned.
- [x] 3.4 Ensure selecting OpenAI search does not alter model, vision, judge or embedding provider selection.

## 4. Tests

- [x] 4.1 Add or update provider selection tests for `SEARCH_PROVIDER=openai` returning `OpenAISearchProvider`.
- [x] 4.2 Add missing credential tests showing OpenAI credentials are required only for the selected search role.
- [x] 4.3 Add OpenAI search parsing tests with fake Responses API URL citation annotations.
- [x] 4.4 Add or preserve tests proving mock search remains the default and health/dependency reporting behavior is unchanged.
- [x] 4.5 Run the relevant backend test suite and fix any regressions.
