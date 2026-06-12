## Why

Operators need to run the backend with Gemini handling model generation, vision analysis, judge evaluation and grounded web search while keeping embeddings on the existing OpenAI embedding provider. The current role-based provider system already supports Gemini for model, vision and judge roles, but rejects `SEARCH_PROVIDER=gemini`, causing `/assistant/chat` to fail during provider registry construction for the desired all-Gemini-except-embeddings runtime.

This change closes that provider gap and makes the search trust policy explicit. Gemini search must be citation-backed through Google Search grounding, mapped into the existing `SearchProvider` interface, and compatible with the assistant's trusted evidence pipeline without adding Gemini embeddings or changing the existing role separation.

## What Changes

- Add a Gemini-backed implementation of the existing `SearchProvider` interface.
- Support `SEARCH_PROVIDER=gemini` in the provider factory.
- Add `GEMINI_SEARCH_MODEL` with a Flash-class default so search can be tuned independently from text, vision and judge roles.
- Require `GEMINI_API_KEY` when the search provider is Gemini.
- Use Gemini Google Search grounding for search; ungrounded Gemini generation is not an acceptable search fallback.
- Map Gemini grounded citations into internal `SearchResult` values with title, URL, snippet and source domain.
- Keep `EMBEDDING_PROVIDER=gemini` unsupported; the production embedding path remains `EMBEDDING_PROVIDER=openai`.
- Make the all-Gemini-except-embeddings configuration a supported provider-registry scenario:
  - `MODEL_PROVIDER=gemini`
  - `VISION_PROVIDER=gemini`
  - `JUDGE_PROVIDER=gemini`
  - `SEARCH_PROVIDER=gemini`
  - `EMBEDDING_PROVIDER=openai`
- Update `trusted_web_search` semantics to be trusted-first for all search providers: allowed-domain results are used exclusively when present, and at most one external fallback result may be selected only when no allowed-domain search results are returned.
- Persist external fallback evidence as lower-confidence auto-ingested knowledge and mark fallback source records with `validation_status=external_fallback`.
- Do not trigger external fallback because trusted pages fail to fetch; this change only permits fallback when the search results contain zero allowed-domain results.
- Update environment examples, deployment templates and docs so the intended configuration is clear.
- Add deterministic tests for provider construction, Gemini citation parsing, trusted-first fallback selection and external fallback ingestion metadata.

## Capabilities

### New Capabilities

- `gemini-search-provider`: Defines Gemini-backed web search provider selection, Gemini search model configuration, Google Search grounding requirements, grounded citation mapping and the all-Gemini-except-embeddings provider registry scenario.

### Modified Capabilities

- `assistant-agent`: Changes trusted web fallback behavior so assistant web search uses allowed-domain results first and may select at most one external fallback result only when no allowed-domain search results exist.
- `knowledge-rag-acquisition`: Changes fallback evidence persistence so selected external fallback evidence may be auto-ingested with lower confidence and `validation_status=external_fallback`, while trusted-domain evidence keeps existing trusted ingestion behavior.

## Impact

- Backend provider settings and factory construction gain a Gemini search role and a new `GEMINI_SEARCH_MODEL` setting.
- `app.providers.gemini` gains a `GeminiSearchProvider` that depends on the existing `google-genai` backend dependency.
- Assistant search tooling applies trusted-first result selection consistently across mock, OpenAI and Gemini search providers.
- Knowledge fallback ingestion needs to preserve source-level validation status for external fallback evidence and use lower confidence for that evidence.
- Tests in provider, assistant and knowledge/RAG areas need updates to cover the new configuration, grounded citation mapping and fallback policy.
- Deployment and local configuration documentation need updates to show Gemini for model, vision, judge and search while embeddings remain OpenAI or mock.
