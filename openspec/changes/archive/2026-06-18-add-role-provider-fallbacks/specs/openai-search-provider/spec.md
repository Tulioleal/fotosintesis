## ADDED Requirements

### Requirement: OpenAI search chain compatibility

The OpenAI search provider SHALL participate in ordered search provider chains through the existing `SearchProvider` interface without changing callers or search result contracts. OpenAI search SHALL be usable as either the first provider attempted or a later fallback provider according only to `SEARCH_PROVIDERS` order.

#### Scenario: OpenAI search used as first configured provider

- **WHEN** `SEARCH_PROVIDERS` lists OpenAI first
- **THEN** the fallback wrapper invokes the OpenAI search provider as the primary search attempt
- **AND** callers receive normalized `SearchResult` values using the same contract as a directly selected OpenAI search provider

#### Scenario: OpenAI search used after prior provider failure

- **WHEN** `SEARCH_PROVIDERS` includes OpenAI after another configured search provider
- **AND** the earlier provider fails with a technical fallback-eligible failure
- **THEN** the fallback wrapper can invoke the OpenAI search provider through the existing `SearchProvider.search()` contract
- **AND** callers receive normalized `SearchResult` values using the same contract as a directly selected OpenAI search provider

#### Scenario: OpenAI search failure participates in fallback observability

- **WHEN** an OpenAI search attempt in a provider chain fails or times out
- **THEN** the backend records the failure with provider name, role, operation, latency, request correlation, and sanitized error category
- **AND** the fallback wrapper may attempt the next configured search provider when one is available

#### Scenario: OpenAI search invalid output is technical failure

- **WHEN** OpenAI search returns no usable citation annotations or cannot normalize usable search results
- **THEN** the search provider reports invalid search output for fallback purposes
- **AND** downstream assistant evidence validation does not treat that output as usable web evidence
