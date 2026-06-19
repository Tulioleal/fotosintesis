## Why

Assistant retrieval and web fallback currently use the full scientific name when `plant_binomial_name` is missing. Full taxonomic names with botanical authorship or infraspecific suffixes make operational queries overly specific and can reduce retrieval quality for broadly relevant plant-care evidence.

## What Changes

- Derive a concise binomial operational plant name from `plant_scientific_name` when explicit `plant_binomial_name` is absent.
- Prefer operational names in the order: explicit binomial, derived binomial from scientific name, then normalized scientific name only when a safe binomial cannot be derived.
- Keep display-oriented plant naming unchanged so UI-facing responses can still preserve common names and full scientific context.
- Preserve missing-taxonomy behavior when no confirmed taxonomy is available.
- Add regression coverage for botanical authority names, infraspecific names, explicit binomial precedence, and blank taxonomy values.

## Capabilities

### New Capabilities

### Modified Capabilities

- `assistant-agent`: Operational taxonomy selection derives binomial names from full scientific names before RAG, trusted web search, embeddings, indexing, and tool operations.
- `knowledge-rag-acquisition`: Runtime retrieval, trusted web fallback, and fallback claim ingestion use derived binomial operational names when explicit binomial context is missing.
- `structured-plant-data-lookup`: Explicit structured lookup flows receive the same derived binomial operational name fallback when no explicit binomial is supplied.

## Impact

- Affected backend code: `backend/app/assistant/graph.py` name normalization and operational name helpers.
- Affected tests: `backend/tests/test_assistant_agent.py` assistant retrieval/web fallback taxonomy behavior.
- No API contract changes are required for this change; frontend profile persistence/exposure of `binomial_name` remains a later improvement.
