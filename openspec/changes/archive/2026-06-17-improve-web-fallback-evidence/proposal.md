## Why

The assistant web fallback often fails to produce useful answers because it can pass weak snippets, failed fetches, or unrelated taxonomy pages to the answerability judge instead of direct aspect-relevant care evidence. This makes live web fallback slow, opaque, and overly likely to return insufficient evidence even when useful web sources exist.

## What Changes

- Add structured diagnostics for web fallback, including generated query, selected URLs, domains, fetch status, fetch errors, fetched content length, snippet length, evidence length, and timings.
- Treat snippet-only results as weak evidence unless the snippet directly covers the requested aspect.
- Improve or replace the simple page evidence fetcher so trusted pages yield meaningful readable text more reliably.
- Add or prioritize approved care-oriented sources while keeping fetch limits and trusted-source validation in place.
- Stop blocking web fallback answers solely because combined web validation confidence is below the configured threshold; keep confidence as informational metadata.
- Avoid duplicate live web searches by reusing search/acquisition candidates where possible.
- Add tests for snippet-only evidence, page fetch failures, duplicate search avoidance, low-confidence useful web evidence, and real care fallback scenarios.
- Do not add per-aspect query expansion in this change.

## Capabilities

### New Capabilities

### Modified Capabilities

- `assistant-agent`: Improve web fallback behavior so only direct usable evidence can support answers, low web confidence is informational rather than blocking, and duplicate searches are avoided when possible.
- `provider-observability`: Add structured web fallback and page evidence extraction diagnostics.
- `knowledge-rag-acquisition`: Preserve or expose search/acquisition candidates so assistant web fallback can reuse them instead of issuing redundant searches.
- `gemini-search-provider`: Ensure search results expose enough metadata for downstream evidence diagnostics and source selection.

## Impact

- Affected backend code: assistant graph web fallback, assistant tools, trusted page evidence fetcher, knowledge acquisition result plumbing, provider search result handling, settings for trusted sources if care-oriented sources are added.
- Affected tests: assistant-agent tests, knowledge/page evidence tests, provider search tests, and observability/logging assertions.
- Runtime impact: potentially better page extraction and more diagnostics; latency must be controlled with capped concurrent fetches, timeouts, and search reuse.
- No public API contract change is expected.
