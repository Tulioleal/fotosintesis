## ADDED Requirements

### Requirement: Trusted page fetch safety

The system MUST fetch trusted page evidence only from HTTPS URLs that remain trusted after redirects, and MUST fall back to the trusted search snippet when fetched content is unavailable or unsafe.

#### Scenario: Non-HTTPS URL rejected before fetch

- **WHEN** trusted page evidence is requested for a non-HTTPS URL
- **THEN** the system rejects the page fetch before opening a network request and keeps the trusted snippet available as fallback evidence

#### Scenario: Untrusted URL not fetched

- **WHEN** trusted page evidence is requested for a URL that is not approved or explicitly validated as trusted
- **THEN** the system does not fetch the URL and reports degraded evidence for that result

#### Scenario: Unsupported content type

- **WHEN** a trusted HTTPS page returns a content type outside the supported evidence formats
- **THEN** the system rejects fetched content and keeps the trusted snippet available as fallback evidence

#### Scenario: Oversized response

- **WHEN** a trusted HTTPS page response exceeds the configured maximum response size
- **THEN** the system rejects fetched content and keeps the trusted snippet available as fallback evidence

#### Scenario: Trust-crossing redirect

- **WHEN** a trusted HTTPS page redirects to a URL that is not trusted
- **THEN** the system rejects fetched content and keeps the trusted snippet available as fallback evidence

## MODIFIED Requirements

### Requirement: Acquisition degradation

The system MUST NOT block the user experience completely when trusted acquisition, trusted page fetching or LlamaIndex pgvector retrieval fails.

#### Scenario: Trusted acquisition fails

- **WHEN** no trusted source is found or persistence fails
- **THEN** the system returns the best available partial result with limitations and a retry or manual search path

#### Scenario: Trusted page fetch fails

- **WHEN** a trusted source search result is available but page fetching fails because of network, redirect, content type, size, extraction or implementation errors
- **THEN** the system keeps responding with degraded trusted snippet evidence instead of blocking the assistant response

#### Scenario: LlamaIndex retrieval fails

- **WHEN** the LlamaIndex pgvector retriever cannot query or index evidence
- **THEN** the system returns a degraded result with a limitation notice and retry or manual search path instead of silently using SQL-only vector retrieval as the successful path
