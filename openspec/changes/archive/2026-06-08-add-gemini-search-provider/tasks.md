## 1. Configuration

- [x] 1.1 Add `gemini_search_model` to backend settings.
- [x] 1.2 Set the default `GEMINI_SEARCH_MODEL` to `gemini-2.5-flash`.
- [x] 1.3 Update `backend/.env.example` with `GEMINI_SEARCH_MODEL`.
- [x] 1.4 Update deployment config templates/placeholders with `GEMINI_SEARCH_MODEL`.
- [x] 1.5 Update local/deployment docs to show the all-Gemini-except-embeddings production configuration.

## 2. Gemini Search Provider

- [x] 2.1 Add `GeminiSearchProvider` to `app.providers.gemini` implementing `SearchProvider`.
- [x] 2.2 Reuse existing Gemini client construction, provider logging and `GeminiProviderError` handling.
- [x] 2.3 Implement Gemini Google Search grounding invocation for search calls.
- [x] 2.4 Include `allowed_domains` as Gemini search prompt guidance or grounding configuration where supported.
- [x] 2.5 Map grounded Gemini URL citations into internal `SearchResult` values.
- [x] 2.6 Deduplicate repeated citation URLs.
- [x] 2.7 Ignore malformed citation URLs.
- [x] 2.8 Return an empty list when grounding succeeds but yields no valid URL citations.
- [x] 2.9 Raise a clear `GeminiProviderError` when Gemini search grounding or grounded citation metadata is unavailable.
- [x] 2.10 Ensure ungrounded Gemini generation is not used as a search fallback.

## 3. Provider Factory

- [x] 3.1 Import `GeminiSearchProvider` in the provider factory.
- [x] 3.2 Support `SEARCH_PROVIDER=gemini` in `_build_search_provider`.
- [x] 3.3 Require `GEMINI_API_KEY` only when the selected search provider is Gemini.
- [x] 3.4 Pass `settings.gemini_search_model` to `GeminiSearchProvider`.
- [x] 3.5 Preserve existing `mock` and `openai` search provider behavior.
- [x] 3.6 Preserve `EMBEDDING_PROVIDER=gemini` as unsupported.

## 4. Trusted-First Assistant Search Policy

- [x] 4.1 Add or update assistant/tool-layer helper logic to partition search results into allowed-domain and external results.
- [x] 4.2 Use only allowed-domain results when at least one allowed-domain result is returned.
- [x] 4.3 Select at most one external fallback result when zero allowed-domain results are returned.
- [x] 4.4 Apply trusted-first selection consistently for all configured search providers.
- [x] 4.5 Preserve the existing `trusted_web_search` public tool name and call-site compatibility.
- [x] 4.6 Ensure trusted page fetch failures do not trigger external fallback selection in this change.

## 5. External Fallback Persistence

- [x] 5.1 Preserve trusted-domain fallback evidence ingestion with existing trusted source metadata.
- [x] 5.2 Persist selected external fallback evidence with `review_status=auto_ingested`.
- [x] 5.3 Persist selected external fallback evidence with lower confidence than trusted-domain web evidence.
- [x] 5.4 Mark selected external fallback source records with `validation_status=external_fallback`.
- [x] 5.5 Ensure unselected external results are not persisted, chunked, embedded or indexed.
- [x] 5.6 Keep fallback evidence ingestion best effort so persistence failures do not block usable assistant answers.

## 6. Tests

- [x] 6.1 Update provider factory tests so `SEARCH_PROVIDER=gemini` constructs `GeminiSearchProvider` with valid Gemini credentials.
- [x] 6.2 Add provider registry test for `MODEL_PROVIDER=gemini`, `VISION_PROVIDER=gemini`, `JUDGE_PROVIDER=gemini`, `SEARCH_PROVIDER=gemini` and `EMBEDDING_PROVIDER=openai`.
- [x] 6.3 Add missing credential test for `SEARCH_PROVIDER=gemini` without `GEMINI_API_KEY`.
- [x] 6.4 Update tests so Gemini remains unsupported for embeddings.
- [x] 6.5 Add fake Gemini SDK tests for grounded citation mapping into `SearchResult`.
- [x] 6.6 Add fake Gemini SDK tests for malformed citation URL filtering.
- [x] 6.7 Add fake Gemini SDK tests for duplicate citation URL deduplication.
- [x] 6.8 Add fake Gemini SDK tests for no-valid-citation empty results.
- [x] 6.9 Add fake Gemini SDK tests for grounding unavailable failure behavior.
- [x] 6.10 Add assistant/tool tests proving allowed-domain results take precedence over external results.
- [x] 6.11 Add assistant/tool tests proving at most one external fallback result is selected when no allowed-domain results exist.
- [x] 6.12 Add assistant/tool tests proving trusted page fetch failure does not trigger external fallback selection.
- [x] 6.13 Add knowledge ingestion tests proving selected external fallback evidence uses lower confidence and `validation_status=external_fallback`.

## 7. Verification

- [x] 7.1 Run `pytest tests/test_system_providers.py` from `backend/`.
- [x] 7.2 Run assistant/tool tests affected by trusted-first web fallback from `backend/`.
- [x] 7.3 Run knowledge/RAG tests affected by fallback evidence ingestion from `backend/`.
- [x] 7.4 Document or perform a manual smoke test with real Gemini credentials for `SEARCH_PROVIDER=gemini`.
