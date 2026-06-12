## ADDED Requirements

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
