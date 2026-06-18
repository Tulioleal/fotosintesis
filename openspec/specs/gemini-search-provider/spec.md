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

### Requirement: Search result diagnostic metadata

The Gemini search provider SHALL expose enough normalized result metadata for downstream web fallback diagnostics and source selection. At minimum, each returned result SHALL preserve title, URL, snippet, source domain, and whether the snippet was derived from grounding support text or fallback citation metadata when that information is available.

#### Scenario: Grounding support snippet is available

- **WHEN** Gemini grounding metadata includes support text for a citation
- **THEN** the provider returns the support text as the result snippet
- **AND** downstream diagnostics can distinguish that the snippet came from grounding support text when metadata supports that distinction

#### Scenario: Only citation title is available

- **WHEN** Gemini grounding metadata includes a valid URL but no support snippet
- **THEN** the provider may return the title as a fallback snippet
- **AND** downstream diagnostics can identify that the result lacks a substantive snippet when metadata supports that distinction

#### Scenario: Duplicate citations are returned

- **WHEN** Gemini grounding metadata contains duplicate citation URLs
- **THEN** the provider returns each URL only once while preserving the first available title, snippet and source domain

### Requirement: Gemini search remains bounded for fallback use

The Gemini search provider SHALL continue using grounded search only and SHALL NOT perform additional page fetching itself. Page fetching, extraction, trust validation and snippet-only evidence decisions SHALL remain in the assistant evidence layer.

#### Scenario: Gemini returns grounded URLs

- **WHEN** Gemini search returns grounded URLs
- **THEN** the provider returns normalized search results without fetching page content
- **AND** assistant evidence fetching remains responsible for extracting page text

#### Scenario: Grounding unavailable

- **WHEN** Gemini grounding metadata is unavailable
- **THEN** the provider fails clearly and does not return ungrounded generated URLs

### Requirement: Gemini search domain guidance

The Gemini search provider SHALL accept existing search keyword arguments, including `allowed_domains`, without changing the public search interface.

#### Scenario: Allowed domains supplied

- **WHEN** a caller invokes Gemini search with `allowed_domains`
- **THEN** the provider includes the allowed domains as search guidance or grounding configuration where supported
- **AND** the provider still returns normalized results for backend trusted-source selection and validation

### Requirement: Gemini search unusable output classification

The Gemini search provider SHALL classify unusable normalized search output as invalid provider output for fallback purposes rather than silently returning results that cannot satisfy downstream search evidence needs.

#### Scenario: Gemini search chain position determines behavior

- **WHEN** `SEARCH_PROVIDERS` lists Gemini first
- **THEN** the fallback wrapper invokes Gemini search as the primary search attempt
- **AND** when `SEARCH_PROVIDERS` lists Gemini after another configured provider, the fallback wrapper invokes Gemini search only after earlier configured providers fail or are skipped

#### Scenario: Redirect-only grounding URLs are unusable

- **WHEN** Gemini grounding returns only internal redirect, grounding, or provider-control URLs instead of usable external source URLs
- **THEN** the Gemini search provider reports invalid search output for the search-provider contract
- **AND** a configured search fallback wrapper may attempt the next search provider

#### Scenario: No usable normalized results

- **WHEN** Gemini search completes but normalization produces no usable `SearchResult` values for downstream trusted-source selection
- **THEN** the Gemini search provider reports invalid or empty unusable provider output for fallback purposes
- **AND** the assistant evidence layer does not treat that provider response as usable web evidence

#### Scenario: Mixed usable and unusable citations

- **WHEN** Gemini search returns both usable external source URLs and unusable internal redirect or malformed URLs
- **THEN** the provider returns only the usable normalized search results
- **AND** the presence of ignored unusable citations does not trigger provider fallback by itself

#### Scenario: Grounding unavailable remains failure

- **WHEN** Gemini Google Search grounding or grounded citation metadata is unavailable
- **THEN** the provider fails clearly according to existing Gemini search behavior
- **AND** a configured search fallback wrapper may attempt the next search provider
