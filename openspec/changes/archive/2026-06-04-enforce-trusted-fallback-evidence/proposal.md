## Why

Assistant fallback web evidence persistence currently builds knowledge documents from every usable search result, bypassing the trusted-source validation used by the main acquisition flow. This can persist untrusted web content even though fallback persistence is specified to use trusted web-search results and existing trusted ingestion rules.

## What Changes

- Enforce existing trusted-source validation before assistant fallback web results are accepted for persistence.
- Ensure untrusted fallback results are not added to persisted web evidence or ingested into the knowledge vector index.
- Pass configured trusted domains to web search where supported so providers can prefer or restrict trusted results earlier.
- Preserve best-effort fallback answer behavior: untrusted or failed persistence must not block the assistant response.
- Add tests proving untrusted fallback results are not persisted and trusted fallback results still ingest successfully.

## Capabilities

### New Capabilities

### Modified Capabilities

- `knowledge-rag-acquisition`: Assistant fallback web evidence persistence must apply trusted-source validation before storing or indexing web-search evidence.

## Impact

- Affects fallback search orchestration in `backend/app/assistant/graph.py` and fallback evidence ingestion in `backend/app/assistant/tools.py`.
- Reuses `TrustedSourceValidator` and existing trusted-domain configuration from the knowledge acquisition path.
- Updates backend assistant or knowledge acquisition tests to cover trusted and untrusted fallback persistence behavior.
