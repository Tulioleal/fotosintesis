## Why

Trusted page evidence fetches currently fail before network handling because `TrustedPageEvidenceFetcher` does not store its configured redirect limit. This forces assistant fallback answers to degrade to citation snippets even when trusted fetched page content should be available.

## What Changes

- Fix the fetcher initialization bug by preserving the configured `max_redirects` value.
- Add focused regression coverage that exercises the real fetch path and proves the missing attribute no longer raises `AttributeError`.
- Add fallback-answer coverage proving successful fetched trusted page content is used when present.
- Preserve degraded behavior when fetches fail or fetched pages are unsafe, unsupported, oversized or redirect across trust boundaries.
- Add focused fetcher safety tests without changing the trusted source list or source-selection behavior.
- Improve internal observability for fetch failures only if it fits existing logging patterns.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `knowledge-rag-acquisition`: clarify trusted page fetch safety and degraded snippet fallback behavior for page evidence acquisition.
- `assistant-agent`: clarify that fallback answers prefer fetched trusted page content over citation-only snippets when safe content is available, while still responding from snippets on fetch failure.

## Impact

- Affected backend code: `backend/app/knowledge/page_evidence.py`, and possibly assistant fallback-answer wiring in `backend/app/assistant/tools.py` or `backend/app/assistant/graph.py` if tests reveal a gap.
- Affected tests: `tests/test_assistant_agent.py`, `tests/test_knowledge_rag.py`.
- No public API, dependency, trusted-domain, or source-selection changes are expected.
