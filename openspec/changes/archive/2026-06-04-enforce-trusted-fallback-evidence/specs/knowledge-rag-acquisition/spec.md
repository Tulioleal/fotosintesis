## MODIFIED Requirements

### Requirement: Trusted source acquisition

The system MUST restrict incremental acquisition and assistant fallback evidence persistence to approved or explicitly validated trusted sources, regardless of whether search results come from the mock search provider, the configured OpenAI search provider, or assistant fallback web search.

#### Scenario: Untrusted source is sole result

- **WHEN** only blogs, stores, unmoderated forums or non-persistent URLs are available
- **THEN** the system does not use them as the sole basis for persistent knowledge

#### Scenario: OpenAI search returns mixed trust results

- **WHEN** OpenAI-backed search returns both trusted and untrusted source URLs
- **THEN** the acquisition flow uses the existing trusted-source validation rules before persisting or using acquired knowledge

#### Scenario: Assistant fallback persistence receives untrusted web results

- **WHEN** assistant fallback web search returns usable results that fail trusted-source validation
- **THEN** the system does not persist, chunk, embed or index those results as knowledge

#### Scenario: Assistant fallback persistence receives mixed trust results

- **WHEN** assistant fallback web evidence includes both trusted and untrusted source URLs
- **THEN** the system persists, chunks, embeds and indexes only the trusted fallback results through the existing knowledge ingestion path

#### Scenario: Assistant fallback search requests trusted domains

- **WHEN** the assistant runs fallback web search after insufficient RAG evidence
- **THEN** the system passes the configured trusted source domains to the search provider when the provider supports domain filtering
