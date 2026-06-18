## ADDED Requirements

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
