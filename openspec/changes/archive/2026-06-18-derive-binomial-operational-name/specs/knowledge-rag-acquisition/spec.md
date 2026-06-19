## MODIFIED Requirements

### Requirement: RAG acquisition plant name priority
Runtime botanical retrieval, trusted web fallback, and fallback evidence acquisition SHALL use the assistant operational plant name derived from `plant_binomial_name`, then a safe binomial derived from `plant_scientific_name`, then normalized `plant_scientific_name` when no safe binomial can be derived, then `plant` only for legacy flows that already permit plant-only confirmed context.

#### Scenario: RAG retrieval uses binomial name
- **WHEN** an assistant chat request includes `plant_binomial_name` and RAG retrieval is needed
- **THEN** the retrieval query and species/topic context use `plant_binomial_name` as the plant name

#### Scenario: RAG retrieval derives binomial from authority scientific name
- **WHEN** RAG retrieval is needed and `plant_binomial_name` is missing
- **AND** `plant_scientific_name` is `Epipremnum aureum (Linden & André) G.S.Bunting`
- **THEN** the retrieval query and species/topic context use `Epipremnum aureum` as the plant name

#### Scenario: RAG retrieval derives binomial from infraspecific scientific name
- **WHEN** RAG retrieval is needed and `plant_binomial_name` is missing
- **AND** `plant_scientific_name` is `Solanum lycopersicum var. cerasiforme`
- **THEN** the retrieval query and species/topic context use `Solanum lycopersicum` as the plant name

#### Scenario: RAG retrieval falls back to normalized scientific name
- **WHEN** RAG retrieval is needed and `plant_binomial_name` is missing
- **AND** `plant_scientific_name` is present but cannot safely produce a two-token Latin binomial
- **THEN** the retrieval query and species/topic context use the normalized `plant_scientific_name` as the plant name

#### Scenario: Trusted web fallback query uses derived operational name
- **WHEN** persisted RAG evidence is insufficient and trusted web fallback runs for a botanical question
- **AND** `plant_binomial_name` is missing
- **AND** `plant_scientific_name` is `Epipremnum aureum (Linden & André) G.S.Bunting`
- **THEN** the trusted web search query and any fallback evidence ingestion metadata use `Epipremnum aureum` as the assistant operational plant name
- **AND** the trusted web search query does not include the authority text `(Linden & André) G.S.Bunting`

#### Scenario: Legacy plant-only acquisition still works
- **WHEN** an assistant chat request includes only `plant` and retrieval or acquisition is needed in a legacy flow that permits plant-only confirmed context
- **THEN** RAG retrieval, trusted web fallback, and fallback evidence acquisition use `plant` as the plant name
