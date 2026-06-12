## MODIFIED Requirements

### Requirement: Trusted source acquisition

The system MUST restrict incremental acquisition and assistant fallback evidence persistence to approved, explicitly validated trusted sources, or one explicitly marked external fallback source selected by the assistant trusted-first web search policy. External fallback evidence MUST be distinguishable from trusted-domain evidence and MUST NOT be treated as trusted-source evidence.

#### Scenario: Untrusted source is sole result outside fallback policy

- **WHEN** only blogs, stores, unmoderated forums or non-persistent URLs are available outside the assistant external fallback policy
- **THEN** the system does not use them as the sole basis for persistent trusted knowledge

#### Scenario: OpenAI search returns mixed trust results

- **WHEN** OpenAI-backed search returns both trusted and untrusted source URLs
- **THEN** the acquisition flow uses the existing trusted-source validation rules before persisting or using acquired trusted knowledge

#### Scenario: Gemini search returns mixed trust results

- **WHEN** Gemini-backed search returns both allowed-domain and external source URLs
- **THEN** the assistant trusted-first search policy uses allowed-domain results before considering any external fallback result

#### Scenario: Assistant fallback persistence receives untrusted web results outside fallback policy

- **WHEN** assistant fallback web search returns usable results that fail trusted-source validation and are not the selected external fallback result
- **THEN** the system does not persist, chunk, embed or index those results as knowledge

#### Scenario: Assistant fallback persistence receives mixed trust results

- **WHEN** assistant fallback web evidence includes both trusted and untrusted source URLs
- **THEN** the system persists, chunks, embeds and indexes only the trusted fallback results through the existing knowledge ingestion path unless the assistant trusted-first policy selected exactly one external fallback result because no allowed-domain results were available

#### Scenario: Assistant fallback search requests trusted domains

- **WHEN** the assistant runs fallback web search after insufficient RAG evidence
- **THEN** the system passes the configured trusted source domains to the search provider when the provider supports domain filtering or domain guidance

### Requirement: Assistant fallback web evidence persistence

The system SHALL persist assistant fallback web evidence through the existing knowledge ingestion path when selected web-search results are used to answer after insufficient RAG evidence. Trusted-domain fallback evidence SHALL retain trusted provenance, while selected external fallback evidence SHALL be persisted as lower-confidence auto-ingested evidence with source validation status `external_fallback`.

#### Scenario: Trusted fallback evidence is ingested

- **WHEN** the assistant answers a botanical question from trusted-domain web-search results because RAG evidence was insufficient
- **THEN** the system builds a knowledge document from the web snippets or fetched page content and source metadata, marks it `auto_ingested`, and ingests it through the LlamaIndex-backed knowledge vector index
- **AND** the source validation status remains trusted

#### Scenario: External fallback evidence is ingested

- **WHEN** the assistant answers a botanical question from one selected external fallback web result because RAG evidence was insufficient and no allowed-domain search results were returned
- **THEN** the system builds a knowledge document from that fallback evidence and source metadata
- **AND** the document is marked `auto_ingested`
- **AND** the document confidence is lower than trusted-domain web evidence confidence
- **AND** the source validation status is `external_fallback`

#### Scenario: Fallback evidence is embedded and indexed

- **WHEN** fallback web evidence ingestion succeeds
- **THEN** the system chunks, embeds, persists and indexes the evidence using the configured embedding provider so future retrieval can find it

#### Scenario: Fallback evidence persistence is best effort

- **WHEN** fallback evidence ingestion, embedding or indexing fails after usable web evidence was found
- **THEN** the system does not block the assistant answer and records the persistence limitation for observability or response metadata
