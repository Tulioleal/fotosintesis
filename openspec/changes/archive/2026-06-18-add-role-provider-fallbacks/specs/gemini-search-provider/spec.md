## ADDED Requirements

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
