## Context

The backend already isolates runtime AI behavior behind role-specific provider interfaces. `ProviderRegistry` exposes independent providers for model generation, image analysis, judge evaluation, search, embeddings, and plant-data lookups. Gemini is currently implemented for the model, vision and judge roles, while search is implemented only for mock and OpenAI. This makes `SEARCH_PROVIDER=gemini` invalid even though operators can configure the adjacent Gemini roles.

The assistant depends on this registry during `/assistant/chat` handling. `AssistantTools` constructs the registry and calls `trusted_web_search()` when persisted RAG and structured plant-data evidence are insufficient. That tool passes the configured trusted domains to the selected search provider, fetches page evidence, and can ingest fallback evidence into the knowledge vector index through the configured embedding provider.

The desired production configuration is Gemini for model, vision, judge and search, with embeddings kept on OpenAI:

```env
MODEL_PROVIDER=gemini
VISION_PROVIDER=gemini
JUDGE_PROVIDER=gemini
SEARCH_PROVIDER=gemini
EMBEDDING_PROVIDER=openai
```

This design adds Gemini search without replacing the provider abstraction, changing the assistant graph shape, or introducing Gemini embeddings. It also makes the assistant search trust policy deterministic: allowed-domain results are used first, and at most one external fallback result can be selected only when the search provider returns no allowed-domain results.

## Goals / Non-Goals

**Goals:**

- Support `SEARCH_PROVIDER=gemini` as a first-class search provider role.
- Use Gemini Google Search grounding so search results are citation-backed.
- Add `GEMINI_SEARCH_MODEL` as a role-specific search model setting.
- Preserve independent role selection for model, vision, judge, search and embeddings.
- Keep `EMBEDDING_PROVIDER=gemini` unsupported.
- Map Gemini grounded citations into existing `SearchResult` DTOs.
- Keep Gemini SDK details isolated inside `app.providers.gemini`.
- Enforce trusted-first result selection in the assistant/tool layer for all search providers.
- Allow one external fallback result only when no allowed-domain search results exist.
- Persist external fallback evidence as low-confidence `auto_ingested` knowledge with `validation_status=external_fallback` on its source record.
- Update docs, env examples, deployment templates and tests for the all-Gemini-except-embeddings configuration.

**Non-Goals:**

- Add Gemini embeddings or support `EMBEDDING_PROVIDER=gemini`.
- Replace OpenAI embeddings for production vector indexing.
- Add Vertex AI provider configuration.
- Add frontend provider selection.
- Add database-backed provider configuration.
- Add live Gemini integration tests to CI.
- Use ungrounded Gemini generation as a search fallback.
- Automatically fall back to OpenAI, mock search, or ungrounded Gemini when Gemini search grounding fails.
- Rewrite the assistant graph or retrieval pipeline.
- Trigger external fallback because trusted-domain page fetching fails.

## Decisions

1. Add `GeminiSearchProvider` in the existing Gemini provider module.

   `GeminiSearchProvider` will implement `SearchProvider` and live in `app.providers.gemini` alongside `GeminiModelProvider`, `GeminiVisionProvider` and `GeminiJudgeProvider`. It will reuse the existing Gemini client helper, provider-call logging helper and `GeminiProviderError` type. Domain services will continue depending only on `SearchProvider` and `SearchResult`.

   Alternative considered: create a separate Gemini search module. That would reduce file size, but the existing project groups provider implementations by vendor. Keeping Gemini roles together makes factory imports and shared helpers simpler.

2. Require Gemini Google Search grounding for search.

   The search provider must invoke Gemini's search grounding/tooling and derive results from grounded citation metadata. It must not ask the model to generate URLs through normal text generation. If grounding is unavailable, the provider should fail clearly at search-call time with `GeminiProviderError`.

   Alternative considered: best-effort ungrounded Gemini search. That is rejected because the assistant needs citable evidence and the knowledge base must not ingest invented URLs.

3. Validate configuration at provider construction and grounding at call time.

   Factory construction should validate `GEMINI_API_KEY`, construct the SDK client and pass `GEMINI_SEARCH_MODEL`. It should not perform a live search or try to prove grounding availability during registry construction. Grounding support and citation metadata are validated when `search()` is called because they depend on runtime model/API behavior and response contents.

   Alternative considered: perform a startup grounding health check. That would add cost, latency and possible startup failure for transient API conditions. A future optional health check can be added separately if operations need it.

4. Add `GEMINI_SEARCH_MODEL` instead of reusing `GEMINI_TEXT_MODEL`.

   Search is a distinct role with different constraints. Grounding support, latency and cost may vary by model. A separate setting matches the existing role-specific provider pattern and keeps operators from changing text generation behavior just to tune search.

   Alternative considered: reuse `GEMINI_TEXT_MODEL`. That is smaller but couples unrelated roles and makes future model tuning harder.

5. Keep trust policy in the assistant/tool layer.

   `GeminiSearchProvider` should return normalized search results. `AssistantTools.trusted_web_search()` or a nearby helper should partition those results by trusted domains and apply the trusted-first fallback rule. This keeps provider code focused on SDK interaction and applies the same product behavior to mock, OpenAI and Gemini search.

   Alternative considered: enforce fallback inside `GeminiSearchProvider`. That would make Gemini behavior different from OpenAI behavior and place business trust policy inside a vendor adapter.

6. Use deterministic insufficiency for external fallback.

   External fallback is allowed only when the search result set has zero allowed-domain results. It is not triggered by page fetch failure, thin trusted content or model-judged insufficiency in this change.

   Alternative considered: fallback when trusted pages fail to fetch. That is more user-helpful in some cases, but it adds a second-stage policy and more complex tests. Existing degraded behavior remains available when fetches fail.

7. Persist external fallback as low-confidence auto-ingested evidence.

   When an external fallback result is used and persisted, its knowledge document remains `ReviewStatus.auto_ingested`, but with lower confidence than trusted-domain web evidence. Its source receives `validation_status=external_fallback`. This preserves the requested auto-ingestion behavior while making lower-trust provenance visible.

   Alternative considered: mark external fallback as `needs_review`. That is stricter but conflicts with the requested auto-ingest policy. Another alternative was treating fallback as `trusted`; that is rejected because external fallback is not part of the configured trusted-domain set.

8. Keep embeddings on OpenAI or mock.

   The all-Gemini-except-embeddings runtime uses OpenAI embeddings in production. Local and CI flows may continue using mock embeddings. `EMBEDDING_PROVIDER=gemini` remains unsupported and should continue to fail clearly.

   Alternative considered: add Gemini embeddings in the same change. That is out of scope because vector dimensions, persisted embeddings and retrieval behavior would require a separate migration and test strategy.

## Risks / Trade-offs

- Gemini grounding SDK shape may differ from expectations or change across `google-genai` versions. Mitigation: isolate citation parsing helpers, cover multiple fake response shapes where practical, and document a manual smoke test with real credentials.
- Gemini may provide prompt-level domain preference rather than strict domain restriction. Mitigation: enforce allowed-domain selection after provider results return, and treat domain restriction in the provider prompt/tool config as guidance rather than the only guardrail.
- Grounding metadata may be unavailable for some responses. Mitigation: fail clearly when grounding tooling is unavailable; return no search results when grounding runs but yields no valid citations.
- External fallback evidence can introduce lower-trust data into the knowledge base. Mitigation: allow at most one external result, use lower confidence, and set `validation_status=external_fallback`.
- Existing retrieval filters may not distinguish source validation status. Mitigation: use lower confidence now and leave validation-status-aware retrieval as a future follow-up if needed.
- Applying trusted-first fallback to all search providers can change OpenAI search behavior when mixed trusted and external results are returned. Mitigation: the behavior aligns with the existing trusted-search intent and is covered by assistant/tool tests.
- Provider registry construction still fails when selected provider credentials are missing. Mitigation: this is intentional fail-fast configuration behavior and mirrors existing OpenAI/Gemini role validation.

## Migration Plan

1. Add `GEMINI_SEARCH_MODEL` to settings, `.env.example`, deployment config and docs.
2. Add `GeminiSearchProvider` and factory wiring for `SEARCH_PROVIDER=gemini`.
3. Update assistant search result selection and fallback ingestion metadata.
4. Update tests for provider construction, Gemini search mapping, trusted-first fallback and low-confidence external ingestion.
5. Deploy with existing search settings unchanged by default; `SEARCH_PROVIDER` remains `mock` unless explicitly changed.
6. Enable Gemini search in target environments by setting `SEARCH_PROVIDER=gemini`, `GEMINI_API_KEY` and optionally `GEMINI_SEARCH_MODEL`.

Rollback is configuration-only if OpenAI or mock search remains available: set `SEARCH_PROVIDER=openai` or `SEARCH_PROVIDER=mock` and redeploy. If code rollback is needed, revert the change before configuring `SEARCH_PROVIDER=gemini`.

## Open Questions

- Exact `google-genai` Python SDK syntax for Google Search grounding must be verified during implementation.
- Exact Gemini grounded citation metadata paths must be verified during implementation.
- Whether the chosen Gemini search model supports strict domain restriction or only domain guidance must be verified during implementation.
- Whether `0.35` is the right external fallback confidence should be checked against any existing confidence conventions during implementation; it should remain lower than trusted web evidence.
