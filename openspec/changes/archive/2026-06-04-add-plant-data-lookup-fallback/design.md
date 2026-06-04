## Context

The backend assistant currently retrieves botanical evidence through `KnowledgeAcquisitionService` and LlamaIndex pgvector. When retrieval returns insufficient chunks or degrades, `AssistantGraph` proceeds to trusted web search/page fetch and then attempts best-effort ingestion of web evidence. The existing flow already has provider registry seams, deterministic mocks, trusted-source validation and auto-ingested knowledge persistence.

This change inserts structured provider evidence between RAG and trusted web search. It must preserve the confirmation gate from plant identification: structured lookup receives only an already-confirmed scientific name from selected garden context or an explicitly supplied confirmed plant hint, and it must not identify or disambiguate plants.

## Goals / Non-Goals

**Goals:**

- Add a `plant_data_lookup` assistant tool that queries Trefle first and Perenual only when Trefle does not sufficiently cover the requested topic.
- Normalize structured provider responses into the same internal knowledge document/chunk evidence model used by RAG answers.
- Generate concise answers with source/provider attribution from structured API evidence.
- Persist and index structured API evidence best-effort using `ReviewStatus.auto_ingested`, without blocking the user response if persistence or pgvector indexing fails.
- Preserve deterministic tests proving ordering: RAG, Trefle, conditional Perenual, trusted web fallback, then degraded/manual path.

**Non-Goals:**

- Do not add plant identification, visual matching or taxonomic disambiguation to Trefle or Perenual lookup.
- Do not replace GBIF taxonomy validation or the existing confirmation gate.
- Do not require Trefle/Perenual credentials unless a real structured provider is configured for backend runtime.
- Do not expose Trefle/Perenual credentials through frontend configuration or unrelated deployment surfaces.

## Decisions

- Introduce structured plant-data provider interfaces behind the provider registry.
  - Rationale: existing assistant tools already receive configured providers and tests can inject deterministic mocks without network calls.
  - Alternative considered: call Trefle/Perenual directly from `AssistantGraph`; rejected because it would couple orchestration to HTTP clients and make ordering harder to test.

- Keep sufficiency evaluation explicit and topic-aware.
  - Rationale: Trefle may be sufficient for taxonomy, morphology or botanical description but not for watering, sunlight, soil, maintenance or pest-care guidance. Perenual should fill only those care gaps.
  - Alternative considered: always call both APIs; rejected because it adds cost, latency and unnecessary credential/runtime dependency.

- Normalize structured API evidence into `KnowledgeDocumentInput` with provider `KnowledgeSourceInput` records and `ReviewStatus.auto_ingested`.
  - Rationale: this reuses the existing ingestion path, metadata shape and RAG retrieval model, and matches the requirement that API evidence not be marked `needs_review`.
  - Alternative considered: introduce a separate structured evidence persistence table; rejected unless implementation reveals the current model cannot represent provider attribution.

- Add a separate graph fallback node before trusted web search.
  - Rationale: the regression tests need a visible ordering boundary, and trusted web search must only run after structured evidence is unavailable or insufficient.
  - Alternative considered: hide structured lookup inside `KnowledgeAcquisitionService.retrieve_or_acquire`; rejected because the assistant still needs to answer immediately from live structured evidence even if persistence/indexing fails.

## Risks / Trade-offs

- Provider payload fields may vary or be sparse -> Use defensive mappers, topic-aware sufficiency and fall through to trusted web search when normalized evidence is insufficient.
- Structured providers can fail or rate limit -> Treat failures as non-blocking tool failures and continue to trusted web search or degraded response.
- Persisting live structured evidence before re-retrieval may fail -> Generate the current response from normalized in-memory evidence and record ingestion/indexing failures without blocking.
- Scientific-name confirmation can be ambiguous in free text -> Only call `plant_data_lookup` when the graph already has one selected plant or an already-confirmed scientific-name hint; otherwise clarify before lookup.
- Provider credentials increase runtime configuration surface -> Add credentials only to backend settings/provider construction and keep mock provider defaults usable without credentials.

## Migration Plan

- Add structured provider interfaces, real clients and deterministic mock clients.
- Add optional backend settings for Trefle/Perenual credentials and provider selection as needed by the implementation.
- Add assistant tool and graph node before trusted web search.
- Add best-effort persistence/indexing for normalized structured evidence through the existing knowledge ingestion flow.
- Add regression tests for ordering, conditional Perenual calls, no-identification behavior, attribution and ingestion failure tolerance.
- Rollback by disabling the structured provider configuration or removing the graph node, which returns the flow to existing trusted web fallback behavior.
