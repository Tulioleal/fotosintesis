## Context

The backend already isolates model, vision, judge, search and embedding behavior behind provider interfaces. OpenAI-backed implementations exist for model generation, vision analysis and judge evaluation, but search is currently mock-only despite `SEARCH_PROVIDER` already existing in settings. Knowledge acquisition calls the search provider through the existing `SearchProvider.search(query, **kwargs)` interface and then applies trusted-source validation before persisting evidence.

## Goals / Non-Goals

**Goals:**
- Add `SEARCH_PROVIDER=openai` without changing domain-service call sites.
- Mirror the existing OpenAI vision provider setup for settings, factory wiring, credential validation, logging and async client usage.
- Parse OpenAI Responses API web search citations into internal `SearchResult` objects.
- Keep trusted-source validation as the authoritative safety gate after search results are returned.
- Preserve independent role configuration so selecting OpenAI search does not affect model, vision, judge or embedding providers.

**Non-Goals:**
- Replace RAG vector retrieval or introduce embeddings/vector search.
- Change the public `SearchProvider` interface or `KnowledgeAcquisitionService` acquisition flow.
- Guarantee provider-side domain restriction enforcement; backend validation remains required.
- Add new persistence tables or alter knowledge document schemas.

## Decisions

- Implement `OpenAISearchProvider` in `app.providers.openai` rather than a separate module. This keeps OpenAI provider behavior centralized with existing `_client`, `_logged`, response parsing conventions and provider naming.
- Use the OpenAI Responses API web search tool for external web retrieval. This matches the requested OpenAI-backed web search behavior and avoids adding another search vendor or custom scraper.
- Add `openai_search_model` and `OPENAI_SEARCH_MODEL` instead of reusing the text or vision model setting. This keeps each provider role independently configurable and matches the existing role-specific OpenAI settings pattern.
- Update `_build_search_provider` to receive `settings` and validate `OPENAI_API_KEY` only when `SEARCH_PROVIDER=openai`. This preserves mock defaults and avoids requiring credentials for unselected roles.
- Parse URL citation annotations into `SearchResult` values using citation title, URL, surrounding text or response text as snippet material, and the parsed URL hostname as `source_domain`. Invalid or non-URL citations should be ignored.
- Pass `allowed_domains` into the OpenAI request as prompt guidance only. The existing `TrustedSourceValidator` remains the enforcement point because provider-side web search filtering can be incomplete or unavailable.

## Risks / Trade-offs

- OpenAI citation annotation shape may vary across SDK versions or response formats -> Keep parsing defensive and cover the expected fake Responses API shape in tests.
- Web search may return untrusted or non-HTTPS sources -> Preserve post-search `TrustedSourceValidator` filtering and do not treat prompt domain guidance as enforcement.
- OpenAI search calls add network latency and cost -> Keep mock as default and only instantiate OpenAI search when explicitly configured.
- Search result snippets may be less structured than mock results -> Use available citation title/URL/text fields and keep result construction tolerant of missing optional metadata.
- Adding a search model setting increases configuration surface -> Use the same default style as other OpenAI role model settings and document it in `.env.example`.
