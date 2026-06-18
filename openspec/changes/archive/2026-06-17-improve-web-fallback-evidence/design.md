## Context

The assistant has two web-related paths during plant-care chat: knowledge acquisition may run a provider search when local RAG has too little evidence, and assistant fallback may run another trusted web search when answerability validation rejects local evidence. The current web fallback can pass snippet-only evidence to the judge when page fetching fails, and current logs do not clearly show whether failure came from query selection, source selection, fetch failure, extraction failure, or judge validation.

The current implementation also treats combined web validation confidence as a hard threshold for non-safety evidence. That makes web fallback less useful because confidence is not calibrated and can reject otherwise direct source support. The change should make evidence quality stricter while making confidence informational for web fallback.

## Goals / Non-Goals

**Goals:**
- Make web fallback failures diagnosable with structured logs and timing metadata.
- Distinguish fetched page content from snippet-only evidence.
- Prevent weak snippet-only results from being treated as strong usable evidence unless directly aspect-covering.
- Improve page text extraction reliability while keeping fetches bounded.
- Add or prioritize care-oriented trusted sources without making source count the only fix.
- Reuse existing search/acquisition candidates where possible to avoid duplicate provider search calls.
- Treat web validation confidence as informational for non-safety web fallback, while preserving direct aspect coverage and safety constraints.

**Non-Goals:**
- Adding per-aspect web query expansion in this change.
- Removing trusted-source validation.
- Removing answerability judging for web fallback.
- Allowing unsupported general advice to be presented as source-backed evidence.
- Changing public assistant API contracts.

## Decisions

1. Log web fallback as a pipeline, not a single route event.

   The implementation will emit structured logs for query construction, selected search candidates, page fetch/extraction outcomes, evidence package sizes, judge inputs, and reuse decisions. This makes failures actionable. Alternative considered: only increasing log level for existing fetch failures. That would still not connect query, selected URL, fetch outcome, and judge input under one trace.

2. Separate evidence strength from evidence existence.

   A web result with only a snippet will remain visible as a candidate, but it will not count as strong usable evidence unless the snippet directly covers the requested aspect. Fetched page content will be preferred for judge evidence. Alternative considered: rejecting all snippet-only results. That is safer but can discard high-quality grounded snippets from providers when page fetch is blocked.

3. Improve extraction within bounded latency.

   The page evidence fetcher will be improved or replaced to capture readable text more reliably, but fetches must remain capped by result count, timeout, content size, redirects, and trusted-domain validation. Alternative considered: fetching many pages or using unbounded retries. That would likely worsen the 25-35 second request latencies already observed.

4. Add care-oriented sources, but keep quality controls.

   More sources can help only if they are relevant to practical care and still pass trust validation. The trusted source list should prefer persistent care sources over taxonomy-only sources when the fallback asks a practical care question. Alternative considered: adding broad commercial/blog domains indiscriminately. That increases noise and persistence risk.

5. Reuse search candidates before issuing another search.

   When acquisition already performed a search in the same assistant flow, fallback web search should reuse usable candidates or evidence metadata before calling the search provider again. Alternative considered: always search again with a fallback-specific query. That may improve recall, but it doubles latency and cost in common insufficient-RAG paths.

6. Confidence does not block non-safety web fallback by itself.

   For web fallback, direct aspect coverage, source support, contradictions, and safety sensitivity are the gating factors. Confidence remains logged and persisted as metadata. Safety-sensitive aspects retain stricter validation. Alternative considered: lowering the web threshold. That still treats confidence as a hard gate and can reject useful direct evidence.

## Risks / Trade-offs

- [Risk] Accepting low-confidence web evidence could allow weak answers. -> Mitigation: require direct source support for requested aspects, preserve contradiction handling, and keep safety-sensitive requirements strict.
- [Risk] Better page extraction may increase latency. -> Mitigation: cap fetched pages, fetch concurrently, use timeouts, avoid duplicate searches, and log timings per phase.
- [Risk] Snippet-only evidence can still be misleading. -> Mitigation: only allow snippet-only evidence as usable when it directly covers the requested aspect and keep it marked as snippet-derived in diagnostics.
- [Risk] More trusted sources can increase noise. -> Mitigation: prioritize care-oriented sources and keep source-domain validation and persistence restrictions.
- [Risk] Reusing acquisition candidates may reuse generic taxonomy results. -> Mitigation: fallback still runs answerability judging and treats non-aspect-covering evidence as insufficient.
