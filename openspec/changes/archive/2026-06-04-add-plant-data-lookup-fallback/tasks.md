## 1. Provider Interfaces And Configuration

- [x] 1.1 Add structured plant-data provider interfaces and normalized result types for Trefle, Perenual and merged evidence.
- [x] 1.2 Add deterministic mock Trefle and Perenual providers that can return sufficient, insufficient and unavailable responses for regression tests.
- [x] 1.3 Add real Trefle and Perenual provider clients behind backend runtime provider construction.
- [x] 1.4 Add backend-only settings for Trefle/Perenual provider selection and credentials, requiring credentials only when real providers are selected.

## 2. Structured Lookup Service

- [x] 2.1 Implement topic-aware Trefle sufficiency evaluation for botanical/species and care-related topics.
- [x] 2.2 Implement `plant_data_lookup` orchestration that queries Trefle first and calls Perenual only for missing care-specific evidence.
- [x] 2.3 Normalize merged Trefle/Perenual payloads into internal evidence with provider attribution and source metadata.
- [x] 2.4 Ensure the lookup accepts only an already-confirmed scientific name and does not perform identification, matching or disambiguation.

## 3. Assistant Flow Integration

- [x] 3.1 Add `AssistantTools.plant_data_lookup` with non-blocking error reporting.
- [x] 3.2 Insert a structured lookup graph node after insufficient or unavailable RAG retrieval and before trusted web search.
- [x] 3.3 Generate concise structured-evidence answers with provider attribution when normalized evidence is sufficient.
- [x] 3.4 Preserve the existing trusted web search/page-fetch fallback and final manual/degraded response when structured evidence is unavailable or insufficient.

## 4. Persistence And Retrieval Reuse

- [x] 4.1 Persist structured API evidence through the existing knowledge document flow with `ReviewStatus.auto_ingested`.
- [x] 4.2 Index structured evidence into pgvector best-effort for future retrieval without blocking the current user response.
- [x] 4.3 Record persistence or indexing failures as non-blocking tool failures while still answering from sufficient live structured evidence.

## 5. Regression Tests

- [x] 5.1 Add tests proving sufficient RAG evidence prevents Trefle, Perenual and trusted web calls.
- [x] 5.2 Add tests proving insufficient RAG calls Trefle before trusted web search.
- [x] 5.3 Add tests proving Perenual is not called when Trefle is sufficient and is called only when Trefle lacks requested care fields.
- [x] 5.4 Add tests proving trusted web search runs only after structured API evidence is unavailable or insufficient.
- [x] 5.5 Add tests proving no structured API call is made for identification, ambiguous plant context or unconfirmed plant context.
- [x] 5.6 Add tests proving structured evidence is auto-ingested, attributed to providers and resilient to persistence or pgvector indexing failures.

## 6. Verification

- [x] 6.1 Run the backend assistant and knowledge RAG test suites.
- [x] 6.2 Run provider configuration tests covering mock defaults and missing real-provider credentials.
- [x] 6.3 Run OpenSpec validation/status checks for `add-plant-data-lookup-fallback`.
