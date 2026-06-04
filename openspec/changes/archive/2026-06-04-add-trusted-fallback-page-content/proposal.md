## Why

Fallback assistant web evidence currently depends on search result metadata and short snippets, so answer generation and knowledge ingestion can miss the trusted source page body that users expect citations to represent. Fetching and extracting trusted page content improves grounded answers while preserving existing trust boundaries and degraded fallback behavior.

## What Changes

- Validate fallback web-search results with the existing trusted-source validator before any source page fetch or persistence.
- Fetch trusted HTTPS source pages with bounded timeouts, response-size limits and content-type checks.
- Extract readable main text from HTML when possible, normalize and truncate it to a bounded evidence size, and include it in fallback answer evidence.
- Persist fetched trusted page content through the existing knowledge ingestion and vector-index path on a best-effort basis.
- Keep snippet-only fallback behavior when page fetch, extraction or persistence fails.
- Do not change frontend APIs or relax trusted-source domain validation.

## Capabilities

### New Capabilities

### Modified Capabilities
- `knowledge-rag-acquisition`: Fallback trusted source acquisition SHALL fetch, extract, use and persist trusted page content when available while degrading to snippets safely.
- `assistant-agent`: Assistant fallback answer generation SHALL include fetched trusted page content in evidence context when available.

## Impact

- Affected backend assistant fallback web-search/acquisition flow.
- Affected trusted-source validation, page fetching/extraction, knowledge ingestion and vector indexing integration points.
- New or updated backend tests for trusted fetch/persist behavior, untrusted URL rejection, degraded snippet fallback and evidence context inclusion.
- No frontend API changes expected.
