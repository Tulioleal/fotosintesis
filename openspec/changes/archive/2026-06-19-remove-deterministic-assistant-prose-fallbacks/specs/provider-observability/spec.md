## ADDED Requirements

### Requirement: Typed provider and tool failure metadata

Provider and assistant tool failures SHALL expose sanitized typed technical metadata to internal callers so assistant routing can distinguish retryable provider unavailability from semantic fallback reasons. Metadata MUST exclude raw credentials, prompts, full model responses, raw provider payloads and raw evidence, and MUST preserve bounded fields such as provider, role, operation, failure category, transient flag, retryable flag, status code when available, attempt index and sanitized cause type.

#### Scenario: Provider failure metadata is sanitized and typed

- **WHEN** a provider attempt fails
- **THEN** the failure exposed to internal callers includes a typed sanitized failure category and retryability fields
- **AND** the metadata excludes raw credentials, prompts, full model responses and raw provider payloads

#### Scenario: Assistant distinguishes technical and semantic failures

- **WHEN** the assistant receives provider or tool failure metadata
- **THEN** retryable technical provider unavailability remains separate from semantic fallback reasons such as insufficient evidence or unsupported care claims
- **AND** assistant failure routing does not parse user-facing strings to determine retryability

## MODIFIED Requirements

### Requirement: Technical provider fallback

The backend SHALL fail over to the next configured provider in a role chain only for technical provider failures and SHALL NOT fail over for valid semantic decisions. Provider fallback classification MUST inspect typed/original provider failure metadata before wrapper exception text so wrapped transient failures remain eligible for provider fallback and circuit breaker behavior.

#### Scenario: Transient provider failure triggers fallback

- **WHEN** a provider call fails due to timeout, rate limit, service unavailable response, network failure, empty response, or another classified transient technical failure
- **THEN** the fallback wrapper attempts the next healthy configured provider for the same role and operation
- **AND** the caller receives the first successful provider result that satisfies the role interface

#### Scenario: Wrapped Gemini service unavailable triggers fallback

- **WHEN** a Gemini provider call fails with an original or wrapped `503 UNAVAILABLE` service-unavailable error
- **THEN** the fallback wrapper classifies the attempt as transient `service_unavailable`
- **AND** the fallback wrapper attempts the next healthy configured provider when one is available
- **AND** the circuit breaker treats the failure as transient

#### Scenario: Rate limit timeout and network failures remain transient through wrappers

- **WHEN** a provider failure is wrapped after a rate-limit, timeout, network or service-unavailable error
- **THEN** classification preserves the original transient technical category
- **AND** the wrapper does not downgrade the failure to `unknown` solely because the outer exception type is generic

#### Scenario: Invalid structured output triggers fallback after retry

- **WHEN** `generate_json` or `judge_response` returns invalid JSON, invalid structured data, or output that cannot satisfy the declared internal contract
- **THEN** the wrapper retries the same provider once using the structured operation retry path
- **AND** if the retry is still invalid, the wrapper attempts the next healthy configured provider

#### Scenario: Semantic insufficient result does not trigger fallback

- **WHEN** a judge provider returns a structurally valid answerability or evaluation result with semantic status `insufficient`
- **THEN** the wrapper returns that result to the caller
- **AND** the wrapper does not try another provider solely because the semantic decision is insufficient

#### Scenario: Every provider fails

- **WHEN** every configured provider in a role chain fails, is skipped as unhealthy, or cannot satisfy the role operation
- **THEN** the wrapper raises a provider-unavailable failure containing sanitized attempt metadata
- **AND** role-specific callers decide whether to degrade safely or surface the technical failure

### Requirement: Provider fallback observability

The backend SHALL emit structured logs, Prometheus metrics, and diagnostics for provider fallback attempts without exposing secrets or raw provider payloads. Provider fallback diagnostics MUST preserve sanitized typed failure metadata from original provider failures and wrappers so transient technical failures can be audited without parsing prose error messages.

#### Scenario: Fallback attempt is recorded

- **WHEN** a fallback wrapper attempts a provider operation
- **THEN** the backend records provider name, role, operation, attempt index, latency, outcome, sanitized error category when applicable, and request correlation metadata

#### Scenario: Fallback success is recorded

- **WHEN** a later provider succeeds after an earlier provider failed or was skipped
- **THEN** the backend records a fallback success metric and structured log event
- **AND** diagnostics identify the final provider and attempted fallback chain

#### Scenario: Provider failure metric emitted

- **WHEN** a provider attempt fails
- **THEN** the backend increments a provider failure metric labelled by role, provider, operation, and sanitized failure category

#### Scenario: Wrapped transient failure diagnostics preserve original category

- **WHEN** a wrapped provider exception is classified from original typed failure metadata
- **THEN** logs, metrics and diagnostics use the sanitized original failure category such as `service_unavailable`, `rate_limited`, `timeout` or `network`
- **AND** diagnostics may include the wrapper type as sanitized cause metadata without replacing the original category

#### Scenario: Secrets are not logged

- **WHEN** provider fallback logs, metrics, or diagnostics are emitted
- **THEN** they exclude raw credentials, prompts, full model responses, and raw provider payloads
