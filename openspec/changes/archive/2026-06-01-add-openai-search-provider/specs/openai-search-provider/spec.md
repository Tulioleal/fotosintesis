## ADDED Requirements

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
