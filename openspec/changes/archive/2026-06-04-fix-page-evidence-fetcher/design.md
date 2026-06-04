## Context

The assistant uses trusted web search as a fallback when persisted RAG evidence is insufficient. Search results are filtered through `TrustedSourceValidator`, then `TrustedPageEvidenceFetcher` fetches trusted HTTPS pages and extracts readable text for fallback answers and optional ingestion.

The fetcher currently references `self.max_redirects` in `_fetch_sync()` but never assigns it in `__init__()`. This makes every otherwise fetchable page fail with `AttributeError`, causing the assistant to use snippet-only evidence or degrade even when trusted page content is available.

## Goals / Non-Goals

**Goals:**

- Fix the missing redirect-limit assignment in the smallest possible code change.
- Add regression coverage that exercises the actual fetch path and prevents future missing-attribute failures.
- Prove successful trusted fetched content is used in assistant fallback answers when available.
- Prove fetch failures and safety rejections continue to degrade to trusted snippets without blocking responses.
- Keep diagnostics useful for future fetch failures if existing logging patterns support a small internal-only improvement.

**Non-Goals:**

- Changing trusted domains, source selection, search-provider behavior or answer wording beyond what tests require.
- Replacing the page extraction algorithm or adding a new fetch library.
- Persisting additional metadata or changing public APIs.

## Decisions

- Assign `self.max_redirects = max_redirects` in `TrustedPageEvidenceFetcher.__init__()` rather than changing redirect handling.
  - Rationale: the redirect handler already expects this value and the configured default is already defined.
  - Alternative considered: hard-code `MAX_REDIRECTS` in `_fetch_sync()`. This would bypass constructor configuration and reduce testability.
- Test fetch behavior through controlled fakes/subclasses that exercise `fetch()` and `_fetch_sync()` behavior without depending on real external sites.
  - Rationale: tests must catch the missing runtime attribute while remaining deterministic under mock provider settings.
  - Alternative considered: assert the attribute exists after construction. This is weaker and would not prove the fetch path works.
- Keep fetch safety failures as fallback evidence rather than graph failures when the original trusted search result has a snippet.
  - Rationale: existing degraded behavior lets the assistant answer from trusted snippets when page retrieval is blocked, oversized, unsupported or otherwise unavailable.
  - Alternative considered: drop failed fetch results entirely. This would worsen fallback coverage and contradict the requested degradation behavior.
- Add logging only if it follows existing backend patterns and does not expose user-facing details or sensitive content.
  - Rationale: the immediate bug is simple; observability should help diagnosis without creating noisy behavior or leaking fetched page text.

## Risks / Trade-offs

- Fetch tests using urllib fakes may be brittle if they over-specify internals -> keep assertions focused on behavior: no `AttributeError`, rejected unsafe URLs, snippet fallback and extracted-content preference.
- Assistant fallback-answer tests may couple to generated text wording -> assert inclusion/exclusion of distinctive fetched content versus citation/snippet-only markdown rather than exact full answer strings.
- Manual URL reproduction can be environment-dependent -> use it as a verification note, not as a required automated test dependency.

## Migration Plan

No data migration is required. Deploy the code and tests normally. Rollback is a standard code rollback; no persisted state or external contract changes are introduced.

## Open Questions

None.
