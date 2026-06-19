## Context

Assistant care-answer operations already distinguish display plant names from operational taxonomy and prefer `plant_binomial_name` when it is present. When the frontend or stored profile cannot supply a binomial, the backend falls back directly to `plant_scientific_name`, which can include botanical authority text or infraspecific rank suffixes. Those full scientific strings are useful context, but they are too specific for operational retrieval, web fallback search, structured lookup input, embeddings, indexing, and fallback claim ingestion.

## Goals / Non-Goals

**Goals:**
- Add backend-only defensive normalization that derives a safe two-token binomial from full scientific names.
- Route operational assistant taxonomy through a single priority order: explicit binomial, derived scientific-name binomial, normalized scientific name when derivation is unsafe.
- Preserve full scientific names for context and display where they are already used.
- Preserve missing-taxonomy behavior for requests that lack confirmed taxonomy.

**Non-Goals:**
- Persisting or exposing `binomial_name` on plant profiles.
- Changing frontend assistant link construction.
- Performing taxonomic validation, synonym resolution, or plant identification from arbitrary text.
- Expanding web search query generation beyond replacing the operational plant name.

## Decisions

- Add `_binomial_from_scientific_name(value: str | None) -> str | None` near existing plant-name normalization helpers in `backend/app/assistant/graph.py`.
  - Rationale: operational name selection already lives in this module, so keeping derivation local avoids a broader taxonomy utility abstraction for a small defensive fallback.
  - Alternative considered: add canonical-name persistence to `plant_profiles`. That would improve data quality but requires schema/API/frontend work and does not protect older or partial requests by itself.

- Derive only from the first two Latin-name-like tokens after existing whitespace trimming and punctuation-safe tokenization.
  - Rationale: botanical authorship, cultivars, varieties, subspecies, and authority suffixes commonly follow the genus and species epithet. Using only the first two valid tokens converts examples such as `Epipremnum aureum (Linden & André) G.S.Bunting` and `Solanum lycopersicum var. cerasiforme` to their operational binomials without needing a taxonomy parser.
  - Alternative considered: strip specific rank markers and parenthetical authority text with many special cases. That is more complex and still less reliable than the simple safe prefix rule for operational search.

- Treat derivation as safe only when both first tokens look like Latin name components.
  - Rationale: the helper must not turn arbitrary display names or malformed strings into false confirmed taxonomy. If derivation is unsafe, existing normalized scientific-name fallback remains available.
  - Alternative considered: always use the first two whitespace-separated tokens. That could corrupt hybrid, cultivar, or non-Latin values and make debugging harder.

- Update `operational_plant_name()` and `_operational_name_for_tools()` to share the derived-binomial fallback behavior.
  - Rationale: this keeps RAG lookup, web fallback query construction, structured lookup, embeddings, indexing, and claim ingestion aligned.
  - Alternative considered: update only web fallback query construction. That would fix the visible search query but leave persisted retrieval and ingestion metadata inconsistent.

## Risks / Trade-offs

- Valid but unusual scientific names may not pass the conservative two-token check -> Mitigation: fall back to the normalized scientific name instead of dropping confirmed taxonomy.
- Derived binomial may lose infraspecific precision for varieties or subspecies -> Mitigation: this is intentional for broad operational care lookup, while full scientific name context remains available for answer generation and diagnostics.
- Multiple helper call sites may drift if one is missed -> Mitigation: add tests for knowledge search, web query construction, explicit binomial precedence, and missing-taxonomy behavior.

## Migration Plan

No data migration is required. Deploy as a backend behavior change. Rollback is restoring the previous helper priority order.

## Open Questions

- None for this change. Persisting and exposing `binomial_name` on plant profiles remains a separate future improvement.
