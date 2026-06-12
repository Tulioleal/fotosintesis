## Context

The assistant graph currently joins up to three trusted web fallback results into one evidence string and runs aspect validation once. If the combined evidence validates for any missing aspect, all usable web results are retained by `_validated_web_results`, exposed as response sources, supplied to answer generation and passed to `ingest_web_evidence` with one metadata payload.

That behavior can admit unrelated trusted results into prompts and persistence. It also persists broad `covered_aspects` metadata across all selected sources, which can make future aspect-filtered retrieval treat unrelated chunks as validated evidence.

## Goals / Non-Goals

**Goals:**

- Validate each fallback web source independently against the requested missing aspects.
- Ensure only independently validated sources reach answer prompts, response sources and ingestion.
- Persist each validated source independently with source-specific `covered_aspects` and validation confidence.
- Preserve partial coverage when a source validates one requested aspect but not all missing aspects.
- Keep validation cost bounded to the top three usable web results.
- Preserve conservative safety behavior for pet toxicity, human edibility and related safety-sensitive aspects.

**Non-Goals:**

- Changing the assistant chat API shape.
- Changing search provider interfaces or trusted-domain selection policy.
- Reworking RAG retrieval, structured plant-data lookup or taxonomy confirmation beyond the web fallback validation handoff.
- Persisting unvalidated search snippets for offline review.

## Decisions

1. Validate source-level evidence instead of aggregate web evidence.

   The graph will validate each of the top three usable `TrustedPageEvidence` items independently by passing only that source's snippet or fetched page content to the existing semantic judge and deterministic aspect guardrails. This preserves the current validation semantics while preventing cross-source laundering. The alternative, validating the aggregate and then post-filtering by keyword overlap, was rejected because the semantic answerability confidence would still describe the combined blob rather than the individual source.

2. Scope validation to requested missing aspects.

   Each source validation will use a scoped state whose `required_aspects` are the current missing aspects from the RAG and structured-data phases. Covered aspects returned by deterministic guardrails must be a subset of those requested aspects. This prevents a generic or off-topic source from becoming eligible due to unrelated care content. The alternative, validating against the original full required-aspect list, could persist web evidence for aspects already covered by RAG and obscure fallback coverage accounting.

3. Filter before prompt and source metadata construction.

   `fallback_web_search` will store only validated web evidence in `state.web_results` and append only those validated results to `state.sources`. Answer synthesis should continue to build its live-web evidence string from `state.web_results`, so unvalidated sources never enter the model prompt. The alternative, filtering only before ingestion, would still expose off-aspect evidence to generation and response metadata.

4. Carry source-specific validation metadata.

   The validated source representation should retain the original `TrustedPageEvidence` plus its covered aspects and confidence. This can be implemented with a small internal dataclass or normalized dict used inside the graph and ingestion handoff. Overall `web_validation_confidence` should be the minimum confidence across included validated sources so existing confidence semantics remain conservative.

5. Persist one source per document.

   `ingest_web_evidence` should create a separate knowledge document for each independently validated source, with metadata containing only that source's covered aspects and confidence. This prevents one broad document from assigning validated aspect metadata to unrelated chunks. The alternative, one document containing all validated sources with combined metadata, is simpler but keeps broad metadata risks when sources cover different aspects.

6. Keep persistence best effort.

   Persistence, chunking, embedding and vector indexing failures should continue to be non-blocking after a usable fallback answer is generated. The implementation should report failures through existing tool failure plumbing without dropping the answer.

## Risks / Trade-offs

- Increased judge calls during fallback -> Validate only the top three usable web results and run them concurrently.
- Partial coverage can produce more nuanced missing-aspect states -> Compute final coverage as the union of prior covered aspects and source-level validated aspects, then route through existing partial/non-critical or safety fallback handling.
- Ingestion API changes can affect existing tests -> Keep the public `ingest_web_evidence` tool method stable where practical, and add/adjust internal metadata handling to support per-source persistence.
- Source-specific metadata may require small test fixture updates -> Prefer explicit test helpers for validated source metadata to make expected coverage and confidence obvious.
- Safety false positives remain possible with keyword guardrails -> Retain direct-evidence checks and safety thresholds per source before allowing safety-sensitive aspects into prompts or persistence.

## Migration Plan

No database migration is required. Existing persisted web evidence remains as-is. New fallback evidence will be persisted as one document per independently validated source after deployment. Rollback is code-only: revert to aggregate validation and single-document persistence if needed, accepting the known evidence-laundering risk.

## Open Questions

- None.
