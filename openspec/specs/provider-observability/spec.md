## Purpose

Define provider abstraction and observability requirements for Fotosintesis AI, including replaceable AI/search providers, deterministic mocks, structured logs, metrics, health checks and traceable AI flows.

## Requirements

### Requirement: Provider interfaces

The backend MUST depend on internal interfaces for text generation, JSON generation, image analysis, embeddings and judge evaluation instead of provider SDKs in domain logic.

#### Scenario: Provider replaced by configuration

- **WHEN** the configured model, vision or embedding provider changes
- **THEN** domain services continue to call the same internal interface without product-rule changes

### Requirement: Mock providers

The system SHALL provide mock providers for model, vision plant identification, search and embeddings.

#### Scenario: Tests run without real credentials

- **WHEN** local or CI tests run without MaaS credentials
- **THEN** the system uses mock providers and returns deterministic results

### Requirement: Structured observability

The system SHALL emit structured JSON logs for requests, tool runs, provider calls and errors.

#### Scenario: Provider call fails

- **WHEN** a provider call fails or times out
- **THEN** the system records provider name, operation, latency, request correlation and sanitized error details

### Requirement: Health and metrics endpoints

The backend SHALL expose health and metrics endpoints for runtime visibility.

#### Scenario: Health check requested

- **WHEN** `GET /health` is requested
- **THEN** the system returns service status and relevant dependency availability

### Requirement: Traceable AI flows

The system SHALL include tracing hooks around chat, RAG, MaaS, GBIF and ingestion boundaries.

#### Scenario: Chat flow traced

- **WHEN** a chat flow uses retrieval, tools or providers
- **THEN** the system can correlate the flow steps under one trace without exposing secrets
