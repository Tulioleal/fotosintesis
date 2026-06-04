## ADDED Requirements

### Requirement: Trusted fallback page-content acquisition
The system SHALL fetch and extract source page content for fallback web evidence only after each search result passes existing trusted-source validation.

#### Scenario: Trusted page content is fetched for fallback evidence
- **WHEN** fallback web search returns a usable HTTPS result from an approved trusted domain
- **THEN** the system validates the result with the existing trusted-source validator before fetching the page
- **AND** fetches the page using bounded timeouts, response-size limits and content-type checks
- **AND** extracts readable text for use as fallback evidence when extraction succeeds

#### Scenario: Untrusted page is not fetched or persisted
- **WHEN** fallback web search returns a result that does not pass existing trusted-source validation
- **THEN** the system does not fetch the result URL
- **AND** does not include the page content in answer evidence
- **AND** does not persist that result as acquired knowledge

#### Scenario: Unsafe fetch response is rejected
- **WHEN** a trusted result fetch redirects to an untrusted or non-HTTPS URL, exceeds the configured response-size limit, times out, or returns an unsupported content type
- **THEN** the system rejects the fetched page body
- **AND** falls back to the trusted search result snippet for that source without blocking the assistant response

### Requirement: Fetched trusted content ingestion
The system SHALL persist fetched trusted page content through the existing knowledge ingestion and vector-index path when page extraction succeeds.

#### Scenario: Fetched content is persisted as trusted knowledge
- **WHEN** trusted fallback page content is successfully fetched and extracted
- **THEN** the system uses the extracted text as the source evidence for generated knowledge content
- **AND** persists the knowledge document, source metadata, chunks and embeddings through the existing knowledge/vector-index path

#### Scenario: Persistence failure does not block fallback answer
- **WHEN** fetched trusted page content is available but knowledge persistence or embedding fails
- **THEN** the system still returns the fallback assistant answer using available evidence
- **AND** reports the persistence failure as a non-blocking tool failure

### Requirement: Snippet degradation remains available
The system SHALL preserve snippet-only fallback behavior when trusted page fetching or extraction fails.

#### Scenario: Extraction fails for trusted result
- **WHEN** a trusted result cannot be fetched or readable text cannot be extracted
- **THEN** the system uses the trusted result title, snippet and URL as degraded fallback evidence
- **AND** does not persist failed or empty fetched page content as knowledge
