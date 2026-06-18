## MODIFIED Requirements

### Requirement: Structured observability

The system SHALL emit structured JSON logs for requests, tool runs, provider calls, answerability decisions, fallback routing decisions, web fallback diagnostics and errors.

#### Scenario: Provider call fails

- **WHEN** a provider call fails or times out
- **THEN** the system records provider name, operation, latency, request correlation and sanitized error details

#### Scenario: Answerability decision logged

- **WHEN** the assistant evaluates whether RAG or structured evidence directly answers a user question
- **THEN** the system records the evidence type, answerable boolean, missing aspects, fallback reason when applicable and request correlation without exposing secrets

#### Scenario: Web fallback decision logged

- **WHEN** the assistant routes from non-answerable local evidence to trusted web search
- **THEN** the system records the fallback reason and request correlation so operators can confirm that web search was attempted

#### Scenario: Web fallback evidence diagnostics logged

- **WHEN** assistant web fallback builds or reuses web evidence
- **THEN** the system records the generated query when a new query is used, selected URLs, source domains, whether each result had fetched content or snippet-only evidence, sanitized fetch errors, fetched content length, snippet length, evidence length passed to judging, reuse status, and timing metadata
- **AND** the logs do not expose secrets or raw credential values

#### Scenario: Page evidence extraction failure logged

- **WHEN** trusted page evidence fetching or extraction fails for a selected source
- **THEN** the system records the source domain, sanitized URL or URL hash, failure category, error type, and request correlation at an operationally visible level
