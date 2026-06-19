## 1. Operational Name Normalization

- [x] 1.1 Add `_binomial_from_scientific_name(value: str | None) -> str | None` near `_normalize_plant_name()` in `backend/app/assistant/graph.py`.
- [x] 1.2 Implement conservative two-token Latin-name validation that derives `Genus species` from full scientific names with authority text or infraspecific suffixes.
- [x] 1.3 Update `operational_plant_name()` to prefer explicit `plant_binomial_name`, then derived binomial from `plant_scientific_name`, then normalized `plant_scientific_name`.
- [x] 1.4 Update `_operational_name_for_tools()` to use the same derived-binomial fallback and preserve existing missing-taxonomy behavior.

## 2. Context and Retrieval Integration

- [x] 2.1 Verify RAG retrieval and species/topic context receive the derived operational binomial when explicit binomial context is missing.
- [x] 2.2 Verify trusted web fallback query construction uses the derived operational binomial and omits botanical authority text.
- [x] 2.3 Verify fallback claim ingestion, embeddings, indexing, and any structured lookup path that uses assistant operational names receive the normalized operational value.
- [x] 2.4 Keep `display_plant_name()` unchanged and preserve full scientific-name context in taxonomy metadata where already available.

## 3. Tests

- [x] 3.1 Add backend tests showing `Epipremnum aureum (Linden & André) G.S.Bunting` without explicit binomial uses `Epipremnum aureum` for knowledge search and web fallback query construction.
- [x] 3.2 Add backend tests showing `Solanum lycopersicum var. cerasiforme` without explicit binomial uses `Solanum lycopersicum` operationally.
- [x] 3.3 Add backend tests showing explicit `plant_binomial_name` still wins over `plant_scientific_name`.
- [x] 3.4 Add backend tests showing blank or missing taxonomy values still produce the existing missing-taxonomy behavior.

## 4. Verification

- [x] 4.1 Run the relevant assistant agent test subset in `backend/tests/test_assistant_agent.py`.
- [x] 4.2 Run OpenSpec validation or status checks for `derive-binomial-operational-name` and confirm the change is apply-ready.
