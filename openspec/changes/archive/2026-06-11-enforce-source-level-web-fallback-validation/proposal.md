## Why

Trusted web fallback evidence is currently validated as a combined evidence blob, which allows one relevant trusted source to carry unrelated sources into answer synthesis, response metadata and persistence. This conflicts with the evidence-gated contract that persisted and cited web evidence must be relevant to at least one requested care aspect.

## What Changes

- Validate each trusted web fallback source independently against the requested missing care aspects before use.
- Exclude any source that fails semantic validation, falls below threshold, covers no requested aspect or fails safety-sensitive guardrails from answer prompts, response source metadata and ingestion.
- Preserve partial source usefulness by carrying only the source-specific validated aspects forward.
- Persist each validated web source as its own knowledge document with source-specific covered aspects and confidence.
- Compute final answer coverage from the union of validated RAG aspects and independently validated web-source aspects.
- Limit validation cost by validating only the top three usable web fallback results concurrently.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Trusted web fallback evidence must be filtered at source level before prompt construction and response source attribution.
- `knowledge-rag-acquisition`: Assistant fallback web evidence persistence must ingest only independently validated sources, one document per validated source, with source-specific metadata.

## Impact

- Affected backend graph nodes for trusted web fallback validation, final answer evidence construction and response source metadata.
- Affected knowledge ingestion path for assistant fallback web evidence persistence, chunking, embedding and vector indexing.
- No public API or provider interface changes are intended.
- Adds graph-level regression coverage for mixed relevant and off-aspect trusted fallback sources.
