## MODIFIED Requirements

### Requirement: Provider interfaces

The backend MUST depend on internal interfaces for text generation, JSON generation, image analysis, search, embeddings and judge evaluation instead of provider SDKs in domain logic.

#### Scenario: Provider replaced by configuration

- **WHEN** the configured model, vision, search or embedding provider changes
- **THEN** domain services continue to call the same internal interface without product-rule changes

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

### Requirement: OpenAI provider observability

OpenAI-backed provider calls SHALL emit the same structured provider-call logs, metrics and traces as other provider calls without exposing secrets or raw credentials.

#### Scenario: OpenAI call fails

- **WHEN** an OpenAI-backed model, vision, search or judge call fails or times out
- **THEN** the system records provider name, operation, role, latency, request correlation and sanitized error details
