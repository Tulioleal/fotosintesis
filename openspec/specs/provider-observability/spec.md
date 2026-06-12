## Purpose

Define provider abstraction and observability requirements for Fotosintesis AI, including replaceable AI/search providers, deterministic mocks, structured logs, metrics, health checks and traceable AI flows.

## Requirements

### Requirement: Provider interfaces

The backend MUST depend on internal interfaces for text generation, JSON generation, image analysis, search, embeddings and judge evaluation instead of provider SDKs in domain logic.

#### Scenario: Provider replaced by configuration

- **WHEN** the configured model, vision, search or embedding provider changes
- **THEN** domain services continue to call the same internal interface without product-rule changes

### Requirement: Mock providers

The system SHALL provide mock providers for model, vision plant identification, search and embeddings.

#### Scenario: Tests run without real credentials

- **WHEN** local or CI tests run without MaaS credentials
- **THEN** the system uses mock providers and returns deterministic results

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

### Requirement: Health and metrics endpoints

The backend SHALL expose health and metrics endpoints for runtime visibility.

#### Scenario: Health check requested

- **WHEN** `GET /health` is requested
- **THEN** the system returns service status and relevant dependency availability

### Requirement: Traceable AI flows

The system SHALL include tracing hooks around chat, RAG, answerability evaluation, fallback routing, MaaS, GBIF and ingestion boundaries.

#### Scenario: Chat flow traced

- **WHEN** a chat flow uses retrieval, answerability evaluation, tools or providers
- **THEN** the system can correlate the flow steps under one trace without exposing secrets

#### Scenario: Answerability fallback path traced

- **WHEN** RAG evidence is rejected as not answerable and the assistant continues to structured lookup or trusted web search
- **THEN** the system can correlate the retrieval, answerability decision, fallback tool call and final answer under one trace

### Requirement: Independent role provider configuration

The backend SHALL configure model generation, vision analysis, judge evaluation, search and embeddings as independent provider roles.

#### Scenario: OpenAI model does not change retrieval providers

- **WHEN** the model provider is configured as OpenAI and search and embeddings remain configured as mock or another provider
- **THEN** assistant and acquisition flows use OpenAI only for model generation and continue using the configured search and embedding providers

#### Scenario: OpenAI vision does not change model provider

- **WHEN** the vision provider is configured as OpenAI and the model provider remains configured as mock or another provider
- **THEN** plant image analysis uses OpenAI and text or JSON generation continues using the configured model provider

#### Scenario: OpenAI judge does not change runtime generation

- **WHEN** the judge provider is configured as OpenAI and the model provider remains configured as mock or another provider
- **THEN** evaluation judging uses OpenAI and runtime assistant generation continues using the configured model provider

#### Scenario: OpenAI search does not change other provider roles

- **WHEN** the search provider is configured as OpenAI and model, vision, judge or embedding providers remain configured as mock or another provider
- **THEN** acquisition search uses OpenAI and all other roles continue using their configured providers

### Requirement: OpenAI role providers

The system SHALL provide OpenAI-backed implementations for model generation, vision analysis, search and judge evaluation through internal provider interfaces.

#### Scenario: OpenAI model selected

- **WHEN** the configured model provider is OpenAI and valid OpenAI credentials and model settings are present
- **THEN** text generation and JSON generation calls return internal generation result objects populated from OpenAI responses

#### Scenario: OpenAI vision selected

- **WHEN** the configured vision provider is OpenAI and valid OpenAI credentials and model settings are present
- **THEN** image analysis calls return internal image analysis result objects populated from OpenAI responses

#### Scenario: OpenAI judge selected

- **WHEN** the configured judge provider is OpenAI and valid OpenAI credentials and model settings are present
- **THEN** evaluation judge calls return internal judge result objects with score, pass status and reasons populated from OpenAI responses

#### Scenario: OpenAI search selected

- **WHEN** the configured search provider is OpenAI and valid OpenAI credentials and search model settings are present
- **THEN** search calls return internal search result objects populated from OpenAI web search citations

#### Scenario: OpenAI role missing credentials

- **WHEN** a provider role is configured as OpenAI without required OpenAI credentials
- **THEN** provider construction or startup fails with a clear configuration error for that selected role without requiring credentials for unselected roles

### Requirement: OpenAI embeddings provider

The backend SHALL provide an OpenAI-backed implementation for embeddings through the existing internal embedding provider interface.

#### Scenario: OpenAI embeddings selected

- **WHEN** the configured embedding provider is OpenAI and valid OpenAI credentials and embedding model settings are present
- **THEN** embedding calls return internal embedding result objects populated from OpenAI embedding responses

#### Scenario: OpenAI embeddings preserve caller contract

- **WHEN** RAG ingestion, knowledge acquisition or assistant tools request embeddings through the provider registry
- **THEN** those callers continue using `EmbeddingProvider.create_embeddings()` without depending on OpenAI SDK response types

#### Scenario: OpenAI embedding role missing credentials

- **WHEN** the embedding provider is configured as OpenAI without required OpenAI credentials
- **THEN** provider construction or startup fails with a clear configuration error for the embedding role without requiring credentials for unselected roles

### Requirement: OpenAI embedding role independence

The backend SHALL configure OpenAI embeddings independently from model generation, vision analysis, judge evaluation and search provider roles.

#### Scenario: OpenAI embeddings do not change generation providers

- **WHEN** the embedding provider is configured as OpenAI and model, vision and judge providers remain configured as mock or another provider
- **THEN** retrieval and ingestion use OpenAI only for embeddings while generation, image analysis and judging continue using their configured providers

#### Scenario: OpenAI embeddings do not change search provider

- **WHEN** the embedding provider is configured as OpenAI and the search provider remains configured as mock or another provider
- **THEN** trusted-source lookup continues using the configured search provider

### Requirement: Provider role mock defaults

The backend SHALL keep deterministic mock providers as the default for model, vision, judge, search and embeddings when real providers are not selected.

#### Scenario: Local tests run without OpenAI credentials

- **WHEN** local or CI tests run with default provider configuration and no OpenAI credentials
- **THEN** model, vision, judge, search and embedding roles use deterministic mock providers

### Requirement: OpenAI provider observability

OpenAI-backed provider calls SHALL emit the same structured provider-call logs, metrics and traces as other provider calls without exposing secrets or raw credentials.

#### Scenario: OpenAI call fails

- **WHEN** an OpenAI-backed model, vision, search or judge call fails or times out
- **THEN** the system records provider name, operation, role, latency, request correlation and sanitized error details

### Requirement: OpenAI embedding observability

OpenAI-backed embedding calls SHALL emit structured provider-call logs, metrics and traces without exposing secrets or raw credentials.

#### Scenario: OpenAI embedding call fails

- **WHEN** an OpenAI-backed embedding call fails or times out
- **THEN** the system records provider name, operation, role, latency, request correlation and sanitized error details

#### Scenario: OpenAI embedding call succeeds

- **WHEN** an OpenAI-backed embedding call succeeds
- **THEN** the system records sanitized provider-call metadata for the embedding role without logging raw credentials

### Requirement: Gemini role providers

The backend SHALL provide Gemini-backed implementations for model generation, vision analysis and judge evaluation through the existing internal provider interfaces.

#### Scenario: Gemini model selected

- **WHEN** the configured model provider is Gemini and valid Gemini credentials and text model settings are present
- **THEN** text generation and JSON generation calls return internal generation result objects populated from Gemini responses

#### Scenario: Gemini vision selected

- **WHEN** the configured vision provider is Gemini and valid Gemini credentials and vision model settings are present
- **THEN** image analysis calls return internal image analysis result objects populated from Gemini responses

#### Scenario: Gemini judge selected

- **WHEN** the configured judge provider is Gemini and valid Gemini credentials and judge model settings are present
- **THEN** evaluation judge calls return internal judge result objects with score, pass status and reasons populated from Gemini responses

#### Scenario: Gemini role missing credentials

- **WHEN** a provider role is configured as Gemini without required Gemini credentials
- **THEN** provider construction or startup fails with a clear configuration error for that selected role without requiring Gemini credentials for unselected roles

### Requirement: Gemini provider role independence

The backend SHALL configure Gemini model generation, vision analysis and judge evaluation independently from each other and from search and embedding provider roles.

#### Scenario: Gemini model does not change retrieval providers

- **WHEN** the model provider is configured as Gemini and search and embeddings remain configured as mock, OpenAI or another provider
- **THEN** assistant and acquisition flows use Gemini only for model generation and continue using the configured search and embedding providers

#### Scenario: Gemini vision does not change model provider

- **WHEN** the vision provider is configured as Gemini and the model provider remains configured as mock, OpenAI or another provider
- **THEN** plant image analysis uses Gemini and text or JSON generation continues using the configured model provider

#### Scenario: Gemini judge does not change runtime generation

- **WHEN** the judge provider is configured as Gemini and the model provider remains configured as mock, OpenAI or another provider
- **THEN** evaluation judging uses Gemini and runtime assistant generation continues using the configured model provider

#### Scenario: Gemini does not implement search or embeddings

- **WHEN** search or embedding provider configuration is evaluated for this change
- **THEN** Gemini is not treated as a supported search or embedding provider and existing search and embedding behavior remains unchanged

### Requirement: Gemini structured JSON generation

Gemini-backed JSON generation SHALL request structured JSON using the supplied schema when supported, return an internal JSON generation result only for parsed JSON objects and fail with a provider error for invalid or non-object responses.

#### Scenario: Gemini JSON object returned

- **WHEN** Gemini JSON generation returns a valid JSON object matching the requested structured response contract
- **THEN** the provider returns a `JsonGenerationResult` containing that object and sanitized schema metadata

#### Scenario: Gemini JSON response invalid

- **WHEN** Gemini JSON generation returns malformed JSON, non-object JSON or a response that cannot be parsed as the requested object
- **THEN** the provider raises a Gemini provider error instead of returning partial or unstructured data

### Requirement: Gemini provider observability

Gemini-backed provider calls SHALL emit the same structured provider-call logs, metrics and traces as other provider calls without exposing secrets or raw credentials.

#### Scenario: Gemini call fails

- **WHEN** a Gemini-backed model, vision or judge call fails or times out
- **THEN** the system records provider name, operation, role, latency, request correlation and sanitized error details

#### Scenario: Gemini call succeeds

- **WHEN** a Gemini-backed model, vision or judge call succeeds
- **THEN** the system records sanitized provider-call metadata for the selected role without logging raw credentials
