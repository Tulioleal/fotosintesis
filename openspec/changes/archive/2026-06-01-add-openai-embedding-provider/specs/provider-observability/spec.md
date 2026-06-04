## ADDED Requirements

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

### Requirement: OpenAI embedding observability

OpenAI-backed embedding calls SHALL emit structured provider-call logs, metrics and traces without exposing secrets or raw credentials.

#### Scenario: OpenAI embedding call fails

- **WHEN** an OpenAI-backed embedding call fails or times out
- **THEN** the system records provider name, operation, role, latency, request correlation and sanitized error details

#### Scenario: OpenAI embedding call succeeds

- **WHEN** an OpenAI-backed embedding call succeeds
- **THEN** the system records sanitized provider-call metadata for the embedding role without logging raw credentials
