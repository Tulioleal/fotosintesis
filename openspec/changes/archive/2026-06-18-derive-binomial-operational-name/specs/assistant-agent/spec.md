## MODIFIED Requirements

### Requirement: Confirmed taxonomy gate for care answers
The assistant plant-care answer pipeline MUST use confirmed taxonomic context for retrieval, structured lookup, trusted web search, embeddings, and indexing. It SHALL prefer `plant_binomial_name`, SHALL fall back to a safe binomial derived from `plant_scientific_name` when possible, SHALL fall back to normalized `plant_scientific_name` only when no safe binomial can be derived, and MUST NOT use nickname, apodo, display name, or `plant_reference` for evidence operations. Display names and full scientific names MAY be preserved for user-facing answer wording and internal context.

#### Scenario: Binomial taxonomy used for care retrieval
- **WHEN** a plant-care answer request includes `plant`, `plant_binomial_name`, and `plant_scientific_name`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `plant_binomial_name` as the operational taxonomy
- **AND** the user-facing answer may still refer to the display plant name

#### Scenario: Scientific authority taxonomy derives binomial for care retrieval
- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name` as `Epipremnum aureum (Linden & André) G.S.Bunting`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `Epipremnum aureum` as the operational taxonomy
- **AND** the full scientific name remains available as scientific context where already included

#### Scenario: Infraspecific scientific taxonomy derives species binomial for care retrieval
- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name` as `Solanum lycopersicum var. cerasiforme`
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use `Solanum lycopersicum` as the operational taxonomy

#### Scenario: Scientific taxonomy fallback used when binomial cannot be safely derived
- **WHEN** a plant-care answer request omits `plant_binomial_name` but includes `plant_scientific_name`
- **AND** the scientific name cannot safely produce a two-token Latin binomial
- **THEN** retrieval, structured lookup, trusted web search, embeddings, and indexing use the normalized `plant_scientific_name` as the operational taxonomy

#### Scenario: Display name is not used for care evidence operations
- **WHEN** a plant-care answer request includes only a nickname, apodo, display name, or classifier `plant_reference` without confirmed taxonomy
- **THEN** the assistant does not run retrieval, structured lookup, trusted web search, embeddings, or indexing with that name
- **AND** it asks for clarification or reports the inconsistent missing-taxonomy state
