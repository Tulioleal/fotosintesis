## Purpose

Define Gemini-backed search provider configuration, grounding behavior, and provider-selection requirements.

## Requirements

### Requirement: Configurable Gemini search provider

The backend SHALL support `SEARCH_PROVIDER=gemini` as a Gemini-backed implementation of the existing `SearchProvider` interface without changing the configured model, vision, judge or embedding providers.

#### Scenario: Gemini search provider selected

- **WHEN** `SEARCH_PROVIDER` is configured as `gemini` with `GEMINI_API_KEY` and `GEMINI_SEARCH_MODEL`
- **THEN** provider construction returns a Gemini-backed search provider
- **AND** provider construction does not require OpenAI search credentials unless another selected role requires them

#### Scenario: All Gemini roles except embeddings selected

- **WHEN** `MODEL_PROVIDER`, `VISION_PROVIDER`, `JUDGE_PROVIDER` and `SEARCH_PROVIDER` are configured as `gemini`
- **AND** `EMBEDDING_PROVIDER` is configured as `openai`
- **AND** required Gemini and OpenAI credentials are configured
- **THEN** provider construction returns Gemini-backed model, vision, judge and search providers
- **AND** provider construction returns the OpenAI embedding provider

#### Scenario: Gemini search missing credentials

- **WHEN** `SEARCH_PROVIDER` is configured as `gemini` without `GEMINI_API_KEY`
- **THEN** provider construction fails with a clear configuration error for the search role

#### Scenario: Gemini embeddings remain unsupported

- **WHEN** `EMBEDDING_PROVIDER` is configured as `gemini`
- **THEN** provider construction fails with a clear unsupported embedding provider error

### Requirement: Gemini search model configuration

The backend SHALL expose role-specific Gemini search model configuration and use that setting only for Gemini search provider calls.

#### Scenario: Gemini search model default is available

- **WHEN** `GEMINI_SEARCH_MODEL` is not explicitly configured
- **THEN** backend settings provide a Flash-class Gemini search model default

#### Scenario: Gemini search model override is configured

- **WHEN** `SEARCH_PROVIDER` is configured as `gemini`
- **AND** `GEMINI_SEARCH_MODEL` is configured with a custom model name
- **THEN** the Gemini search provider uses the configured search model for search calls
- **AND** the configured Gemini text, vision and judge models are unchanged

### Requirement: Gemini search uses grounding

The Gemini search provider SHALL use Gemini Google Search grounding or equivalent Gemini search grounding tooling to produce citation-backed search results.

#### Scenario: Grounded citations are returned

- **WHEN** Gemini returns grounded URL citations for a search query
- **THEN** the provider returns `SearchResult` values containing title, URL, snippet and source domain values derived from valid citations
- **AND** the provider ignores malformed citation URLs
- **AND** the provider returns duplicate citation URLs only once

#### Scenario: No valid citations are returned

- **WHEN** Gemini search grounding completes but returns no valid URL citations
- **THEN** the provider returns an empty search result list

#### Scenario: Grounding is unavailable

- **WHEN** Gemini Google Search grounding or grounded citation metadata is unavailable for a Gemini search call
- **THEN** the provider fails clearly
- **AND** the provider does not return ungrounded generated URLs
- **AND** the provider does not silently fall back to OpenAI, mock search or ungrounded Gemini generation

### Requirement: Gemini search domain guidance

The Gemini search provider SHALL accept existing search keyword arguments, including `allowed_domains`, without changing the public search interface.

#### Scenario: Allowed domains supplied

- **WHEN** a caller invokes Gemini search with `allowed_domains`
- **THEN** the provider includes the allowed domains as search guidance or grounding configuration where supported
- **AND** the provider still returns normalized results for backend trusted-source selection and validation
