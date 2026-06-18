## Purpose

Define configurable OpenAI-backed web search provider behavior for knowledge acquisition search retrieval.

## Requirements

### Requirement: Configurable OpenAI search provider
The backend SHALL support `SEARCH_PROVIDER=openai` as an OpenAI-backed implementation of the existing `SearchProvider` interface.

#### Scenario: OpenAI search provider selected
- **WHEN** `SEARCH_PROVIDER` is configured as `openai` with valid OpenAI credentials and search model settings
- **THEN** provider construction returns an OpenAI-backed search provider without changing the configured model, vision, judge or embedding providers

#### Scenario: Mock search remains default
- **WHEN** `SEARCH_PROVIDER` is unset or configured as `mock`
- **THEN** provider construction uses the deterministic mock search provider without requiring OpenAI credentials

### Requirement: OpenAI search credentials and model configuration
The backend SHALL expose role-specific OpenAI search model configuration and require OpenAI credentials only when the OpenAI search provider is selected.

#### Scenario: OpenAI search missing credentials
- **WHEN** `SEARCH_PROVIDER` is configured as `openai` without required OpenAI credentials
- **THEN** provider construction fails with a clear configuration error for the search role

#### Scenario: Unselected OpenAI search does not require credentials
- **WHEN** `SEARCH_PROVIDER` is not configured as `openai`
- **THEN** provider construction does not require OpenAI search credentials or model configuration beyond defaults

### Requirement: OpenAI web search result mapping
The OpenAI search provider SHALL use the OpenAI Responses API web search tool and map URL citation annotations into internal `SearchResult` objects.

#### Scenario: Citation annotations returned
- **WHEN** OpenAI returns web search URL citation annotations for a query
- **THEN** the provider returns search results containing title, URL, snippet and source domain values derived from those citations

#### Scenario: Invalid citation annotations returned
- **WHEN** OpenAI returns annotations without usable URLs
- **THEN** the provider ignores invalid annotations and returns only valid search results

### Requirement: Search domain guidance
The OpenAI search provider SHALL accept existing search keyword arguments, including `allowed_domains`, without changing the public search interface.

#### Scenario: Allowed domains supplied
- **WHEN** a caller invokes search with `allowed_domains`
- **THEN** the provider includes the allowed domains as search guidance while returning results for backend trusted-source validation

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
