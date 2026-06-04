## 1. Page Evidence Fetching

- [x] 1.1 Add an internal trusted page-evidence model or wrapper that pairs each `SearchResult` with optional extracted content and fetch/extraction failure state without changing provider or frontend APIs.
- [x] 1.2 Implement a backend page fetch/extract service that enforces HTTPS-only URLs, trusted-domain validation before fetch, bounded redirects, short timeouts, maximum response bytes and textual content-type checks.
- [x] 1.3 Implement readable text extraction for HTML/text responses with whitespace normalization and per-source evidence truncation.
- [x] 1.4 Ensure untrusted, non-HTTPS, oversized, timed-out, unsupported content-type and trust-crossing redirect responses are not used as fetched page content.

## 2. Assistant Fallback Integration

- [x] 2.1 Update assistant fallback web search to validate results before page fetching and produce page-evidence objects for trusted usable results.
- [x] 2.2 Update fallback answer generation to prefer extracted trusted page content and degrade to trusted snippets when page fetching or extraction fails.
- [x] 2.3 Preserve existing source URL reporting and assistant response behavior without frontend API changes.

## 3. Knowledge Ingestion Integration

- [x] 3.1 Update fallback web evidence ingestion to use extracted trusted page content when available and snippet evidence otherwise.
- [x] 3.2 Keep all ingestion and embedding persistence on the existing `KnowledgeVectorIndex.ingest_document` path.
- [x] 3.3 Keep persistence failures non-blocking for fallback answers and report them as tool failures.

## 4. Tests

- [x] 4.1 Add tests proving trusted page content is fetched, extracted and persisted through knowledge ingestion/vector indexing.
- [x] 4.2 Add tests proving untrusted or non-HTTPS URLs are not fetched, included in evidence, or persisted.
- [x] 4.3 Add tests proving fetch, content-type, size or extraction failures fall back to snippets without blocking the assistant answer.
- [x] 4.4 Add tests proving fetched content is included in the assistant fallback evidence context used for answer generation.

## 5. Verification

- [x] 5.1 Run the relevant backend assistant and knowledge RAG tests.
- [x] 5.2 Run OpenSpec validation/status for `add-trusted-fallback-page-content` and confirm the change is apply-ready.
