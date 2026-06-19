## Why

Aspect-specific behavior is currently spread across enum values, validation guidance, web-query construction, snippet/content eligibility checks, threshold selection, and diagnostics. As the required-aspect taxonomy grows, this fragmentation increases the risk that classification, retrieval, validation, and answer generation interpret the same aspect differently.

## What Changes

- Add a centralized, structured metadata registry keyed by `RequiredAspect`.
- Define per-aspect domain, human-readable label, query label, search terms, optional coverage guidance, safety sensitivity, and optional diagnostic label.
- Use registry metadata to provide answerability coverage guidance only for requested aspects that define it.
- Use registry metadata to build targeted web fallback queries with human-readable labels and search terms instead of raw enum names.
- Non-semantic snippet/content eligibility gates ensure trusted evidence reaches the answerability judge for coverage decisions.
- Use registry metadata for safety-sensitive aspect detection where practical.
- Preserve canonical enum identifiers for classifier contracts, judge normalization, and API diagnostics while allowing readable labels in diagnostics.
- Fall back safely to enum-derived values when metadata is missing.

## Capabilities

### New Capabilities

- `aspect-metadata-registry`: Defines the centralized metadata registry contract for `RequiredAspect` semantics and lookup behavior.

### Modified Capabilities

- `assistant-agent`: Plant-care answerability, web fallback, and diagnostics consume aspect metadata while preserving canonical required-aspect identifiers.
- `rag-contextual-validation`: Safety-sensitive validation threshold selection is driven by aspect metadata instead of separate hardcoded aspect sets where practical.

## Impact

- Affected backend assistant modules include required-aspect definitions, answerability judge payload construction, targeted web query construction, safety threshold selection, and diagnostic metadata generation.
- Tests will cover metadata lookup, answerability guidance inclusion, web query text, safety sensitivity, and missing-metadata fallback behavior.
- No provider interface, RAG architecture, web fallback provider behavior, or public `RequiredAspect` enum contract is replaced.
