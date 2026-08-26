## ADDED Requirements

### Requirement: Bounded academic trusted page fetching

Trusted page fetching SHALL require HTTPS, an approved source hostname before and after redirects, bounded redirects, a request timeout, supported text content types, and a bounded response body. The fetcher MUST read no more than the configured maximum bytes plus one overflow-detection byte before rejecting an oversized response.

#### Scenario: Trusted page is within bounds

- **WHEN** an approved HTTPS page and its redirects remain approved and return a supported bounded response
- **THEN** the fetcher returns extracted content and final source metadata

#### Scenario: Response exceeds the byte limit

- **WHEN** a response contains more than the configured maximum bytes
- **THEN** the fetcher stops after the overflow-detection byte
- **AND** rejects the content without buffering the complete response

#### Scenario: Redirect leaves approved sources

- **WHEN** a trusted page redirects to HTTP or an unapproved hostname
- **THEN** the fetched content is rejected

### Requirement: Deterministic new source identity

New enrichment evidence SHALL use one deterministic normalized HTTPS source URL for trust checks, judge source binding, persistence, and content identity. Normalization SHALL lowercase the hostname, remove fragments and default HTTPS ports, use the final approved redirect URL, and retain semantically significant path and query data. Historical source identities MUST NOT be rewritten by this change.

#### Scenario: Equivalent basic URL forms are acquired

- **WHEN** new source URLs differ only by hostname case, fragment, empty path, or default HTTPS port
- **THEN** they converge on one source identity

#### Scenario: Distinct path or query is acquired

- **WHEN** source URLs differ in path or ordered query values
- **THEN** normalization preserves that distinction

### Requirement: Provenance for fetched enrichment content

Accepted fetched evidence SHALL retain final source URL, retrieval time, nullable publication time, and stable source version. Missing or unreliable publication metadata SHALL remain null rather than being invented.

#### Scenario: Fetch has stable version metadata

- **WHEN** a successful fetch supplies usable source-version metadata
- **THEN** accepted evidence stores that version and retrieval timestamp

#### Scenario: Publication time is unavailable

- **WHEN** no reliable publication time is supplied
- **THEN** accepted evidence stores a null publication time
- **AND** remains eligible under policy v1 because policy v1 has no age-expiry rule
