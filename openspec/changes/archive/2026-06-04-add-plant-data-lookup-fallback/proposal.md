## Why

The assistant currently falls from insufficient RAG evidence directly into trusted web acquisition or degraded responses, which can be slower, less structured and harder to attribute for common plant-care questions. Adding a structured plant-data fallback gives the assistant deterministic botanical and care evidence before broad web search while preserving the existing confirmed-plant and safety boundaries.

## What Changes

- Add a `plant_data_lookup` tool in the assistant RAG flow that runs only after vector retrieval is unavailable or insufficient.
- Require the tool to use an already-confirmed scientific name and prohibit it from identifying or disambiguating plants.
- Query Trefle first for botanical/species information relevant to the requested topic.
- Evaluate Trefle sufficiency before calling Perenual, and call Perenual only to complement missing care-specific fields such as watering, sunlight, soil, maintenance, pests or care guidance.
- Normalize merged structured API responses into the internal evidence model with provider attribution for concise answer generation.
- Persist and ingest structured API evidence best-effort through the existing auto-ingested flow without marking it `needs_review` and without blocking the user response if persistence or pgvector indexing fails.
- Preserve the existing fallback order after structured APIs: trusted web search/page fetch, then manual search or degraded response.
- Add backend runtime configuration for Trefle and Perenual credentials only where required.
- Add deterministic mock providers and regression coverage for retrieval ordering, sufficiency decisions, attribution, persistence failure tolerance and the no-identification constraint.

## Capabilities

### New Capabilities

- `structured-plant-data-lookup`: Structured plant-data provider lookup, sufficiency evaluation, evidence normalization and best-effort ingestion for assistant answers.

### Modified Capabilities

- `knowledge-rag-acquisition`: Retrieval and acquisition fallback order changes to insert structured API evidence before trusted web search.
- `assistant-agent`: Assistant tool behavior changes to allow `plant_data_lookup` only for already-confirmed scientific names and not for identification or disambiguation.

## Impact

- Affected backend assistant orchestration, RAG acquisition services, evidence models, provider configuration and tests.
- Adds optional backend runtime credentials for Trefle and Perenual providers.
- Adds deterministic mock implementations for structured plant-data providers.
- No breaking API changes are expected for frontend clients.
