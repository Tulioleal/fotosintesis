## MODIFIED Requirements

### Requirement: Structured observability

The system SHALL emit structured JSON logs for requests, tool runs, provider calls, answerability decisions, fallback routing decisions and errors.

#### Scenario: Provider call fails

- **WHEN** a provider call fails or times out
- **THEN** the system records provider name, operation, latency, request correlation and sanitized error details

#### Scenario: Answerability decision logged

- **WHEN** the assistant evaluates whether RAG or structured evidence directly answers a user question
- **THEN** the system records the evidence type, answerable boolean, missing aspects, fallback reason when applicable and request correlation without exposing secrets

#### Scenario: Web fallback decision logged

- **WHEN** the assistant routes from non-answerable local evidence to trusted web search
- **THEN** the system records the fallback reason and request correlation so operators can confirm that web search was attempted

### Requirement: Traceable AI flows

The system SHALL include tracing hooks around chat, RAG, answerability evaluation, fallback routing, MaaS, GBIF and ingestion boundaries.

#### Scenario: Chat flow traced

- **WHEN** a chat flow uses retrieval, answerability evaluation, tools or providers
- **THEN** the system can correlate the flow steps under one trace without exposing secrets

#### Scenario: Answerability fallback path traced

- **WHEN** RAG evidence is rejected as not answerable and the assistant continues to structured lookup or trusted web search
- **THEN** the system can correlate the retrieval, answerability decision, fallback tool call and final answer under one trace
