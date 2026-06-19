## MODIFIED Requirements

### Requirement: Structured lookup operational plant name
Structured plant-data lookup SHALL use the assistant operational plant name derived from `plant_binomial_name`, then a safe binomial derived from `plant_scientific_name`, then normalized `plant_scientific_name` when no safe binomial can be derived, then `plant` only for legacy flows that already permit plant-only confirmed context. Structured lookup MUST continue to treat that value as already-confirmed plant context rather than an identification request when a flow explicitly uses structured lookup. The normal assistant chat-time plant-care answer path SHALL prefer the same operational plant name for RAG and web evidence operations but SHALL NOT use it to call structured lookup in that path.

#### Scenario: Structured lookup uses binomial name first outside normal chat-time path
- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup and includes `plant_binomial_name`
- **THEN** `plant_data_lookup` is called with `plant_binomial_name` as the scientific-name input

#### Scenario: Structured lookup derives binomial from authority scientific name outside normal chat-time path
- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` is `Epipremnum aureum (Linden & André) G.S.Bunting`
- **THEN** `plant_data_lookup` is called with `Epipremnum aureum` as the scientific-name input

#### Scenario: Structured lookup derives binomial from infraspecific scientific name outside normal chat-time path
- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` is `Solanum lycopersicum var. cerasiforme`
- **THEN** `plant_data_lookup` is called with `Solanum lycopersicum` as the scientific-name input

#### Scenario: Structured lookup falls back to normalized scientific name outside normal chat-time path
- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup, `plant_binomial_name` is missing, and `plant_scientific_name` cannot safely produce a two-token Latin binomial
- **THEN** `plant_data_lookup` is called with the normalized `plant_scientific_name` as the scientific-name input

#### Scenario: Legacy plant fallback remains outside normal chat-time path
- **WHEN** an eligible non-chat-time flow explicitly invokes structured lookup and includes only `plant`
- **THEN** existing plant-only assistant payloads can still call `plant_data_lookup` with `plant` when the plant context is otherwise confirmed

#### Scenario: Chat-time path uses operational name for RAG and web only
- **WHEN** the assistant normal plant-care chat path has operational plant context
- **THEN** it uses that context for RAG retrieval and trusted web search
- **AND** it does not call `plant_data_lookup` in that path
