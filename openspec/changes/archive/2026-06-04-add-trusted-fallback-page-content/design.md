## Context

The assistant fallback path already performs trusted web search when existing RAG evidence is insufficient. Today that path carries `SearchResult` metadata and snippets into answer generation and passes the same snippet-only results into knowledge ingestion. `TrustedSourceValidator` already enforces HTTPS and approved-domain checks, and `KnowledgeVectorIndex.ingest_document` is the existing persistence and pgvector indexing path.

The change inserts a backend-only page-content acquisition step after trusted-source validation and before fallback answer generation or persistence. It must preserve the existing response behavior when fetching, extraction or persistence fails.

## Goals / Non-Goals

**Goals:**
- Reuse `TrustedSourceValidator` before any page fetch, answer evidence expansion or persistence.
- Fetch only trusted HTTPS pages with safe timeout, redirect, response-size and content-type constraints.
- Extract readable HTML text where possible, normalize whitespace and cap evidence length per source and per answer context.
- Use fetched text for fallback answer evidence and best-effort ingestion through the existing knowledge/vector-index path.
- Preserve snippet-only fallback when fetch, extraction or persistence fails.

**Non-Goals:**
- No frontend API or conversation response schema changes.
- No relaxation of trusted domain validation or addition of untrusted content to persisted knowledge.
- No crawler, recursive fetching, JavaScript rendering or long-running background ingestion.
- No new persistence model unless implementation discovers existing schemas cannot represent source content.

## Decisions

- Add a small backend page-content fetch/extract service used by assistant fallback flows. This keeps network safety and extraction policy centralized instead of spreading HTTP and parsing logic through graph and ingestion code.
- Validate search results before fetch and again before persistence. This favors defense in depth over assuming callers always pass prefiltered results.
- Keep `SearchResult` as the public provider output and carry fetched evidence in an internal wrapper or data object. This avoids changing provider interfaces and frontend API contracts.
- Use strict fetch constraints: HTTPS URLs only, trusted host only, short connect/read timeout, bounded redirects that must remain trusted HTTPS, maximum response bytes, and accepted textual content types such as `text/html`, `text/plain` and XHTML. Reject binary or unknown content types.
- Prefer lightweight HTML extraction using available backend dependencies or standard-library parsing if sufficient; add a new dependency only if existing tooling cannot produce readable main text reliably. The extraction result is an evidence optimization, not a blocking requirement.
- Persist fetched content by passing the expanded evidence into the existing knowledge document generation and `KnowledgeVectorIndex.ingest_document` path. If persistence fails, answer generation still uses the best available fetched content or snippets and records a tool failure.

## Risks / Trade-offs

- Network fetches could add latency to fallback responses -> use small per-page timeouts, cap the number of fetched results, and continue with snippets on failure.
- Trusted sites may return large, binary or bot-protected responses -> enforce byte and content-type limits and degrade without blocking.
- HTML extraction may include navigation or boilerplate -> normalize and truncate evidence, and prefer main/article-like text where possible.
- Redirects can cross trust boundaries -> every final URL must remain HTTPS and pass `TrustedSourceValidator` domain rules before content is used or persisted.
- Fetched pages can contain prompt-injection text -> treat page text only as evidence, keep existing assistant safety rules, and do not execute or privilege page instructions.
