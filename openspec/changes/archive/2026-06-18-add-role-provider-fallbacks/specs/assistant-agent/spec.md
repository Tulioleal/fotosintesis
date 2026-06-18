## ADDED Requirements

### Requirement: Assistant provider fallback diagnostics

The assistant SHALL surface provider fallback diagnostics separately from semantic assistant fallback reasons and user-visible tool failure metadata.

#### Scenario: Successful provider fallback is diagnostic metadata

- **WHEN** an assistant request succeeds after a provider fallback chain uses a later provider
- **THEN** assistant diagnostics include the attempted providers, final provider, role, operation, and fallback success status
- **AND** the response does not treat the successful provider fallback as a user-visible tool failure

#### Scenario: Provider fallback metadata is separate from semantic fallback reasons

- **WHEN** an assistant request records RAG insufficiency, web fallback routing, conservative safety fallback, or other semantic fallback reasons
- **AND** a technical provider fallback also occurs
- **THEN** technical provider fallback details are stored under separate provider fallback metadata
- **AND** semantic fallback reason fields retain only assistant routing and evidence-validation reasons

#### Scenario: Conversation message stores provider fallback metadata

- **WHEN** an assistant message is persisted after provider fallback attempts occurred
- **THEN** message metadata includes a `provider_fallbacks` field with sanitized provider attempt and final-provider metadata
- **AND** existing semantic fallback metadata remains compatible

### Requirement: Assistant behavior when all role providers fail

The assistant SHALL preserve safe degraded chat behavior when every provider in a role chain fails while allowing non-chat technical flows to surface provider unavailability where appropriate.

#### Scenario: Chat generation providers unavailable

- **WHEN** `/assistant/chat` cannot complete answer generation because all configured model providers fail or are unavailable
- **THEN** the assistant returns the existing safe degraded response for generation failure
- **AND** records sanitized provider-unavailable metadata without inventing botanical facts

#### Scenario: Fallback renderer providers unavailable

- **WHEN** centralized fallback-response rendering cannot complete because all configured model providers fail or are unavailable
- **THEN** the assistant returns the existing minimal Spanish emergency response
- **AND** records sanitized provider-unavailable metadata without exposing provider internals to the user

#### Scenario: Technical evaluation flow providers unavailable

- **WHEN** a non-chat technical or evaluation flow requires a provider role and all providers for that role fail or are unavailable
- **THEN** that flow may surface provider unavailability as a real technical failure
- **AND** the failure includes sanitized role and provider-chain attempt metadata for diagnostics

### Requirement: Provider fallback does not change evidence semantics

The assistant SHALL keep provider fallback infrastructure separate from answerability, retrieval, and evidence-validation semantics.

#### Scenario: Answerability insufficient remains semantic

- **WHEN** an answerability judge returns a structurally valid `insufficient` result
- **THEN** the assistant follows existing insufficient-evidence routing
- **AND** no provider fallback reason is recorded solely because the semantic status is insufficient

#### Scenario: Final provider output remains validated

- **WHEN** provider fallback selects a later provider for model generation, judge evaluation, or search
- **THEN** the assistant still applies the existing schema validation, answerability normalization, trusted-source validation, and evidence-synthesis rules before using the output

#### Scenario: Provider fallback is not exposed as source evidence

- **WHEN** provider fallback metadata is included in assistant diagnostics
- **THEN** the metadata is not treated as botanical source evidence
- **AND** source attribution remains limited to validated evidence sources
