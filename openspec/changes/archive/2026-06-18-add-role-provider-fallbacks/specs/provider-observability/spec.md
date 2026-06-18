## ADDED Requirements

### Requirement: Role provider chains

The backend SHALL support ordered provider chains for model generation, judge evaluation, search, and vision roles while preserving existing single-provider configuration compatibility. Primary and fallback behavior SHALL be determined only by a provider's position in the configured role chain.

#### Scenario: Provider chain configured for role

- **WHEN** `MODEL_PROVIDERS`, `JUDGE_PROVIDERS`, `SEARCH_PROVIDERS`, or `VISION_PROVIDERS` is configured with an ordered provider list
- **THEN** provider construction uses that order for the corresponding role
- **AND** other provider roles keep their own independent configuration

#### Scenario: Provider position determines primary and fallback behavior

- **WHEN** any supported provider is first in a configured role chain
- **THEN** the backend treats that provider as the primary attempt for that role
- **AND** when any supported provider is configured after the first provider in that role chain, the backend treats it as a fallback attempt for that role
- **AND** no provider name is inherently primary or inherently fallback across all configurations

#### Scenario: Provider order can vary by role

- **WHEN** the same provider appears first for one role and later in the chain for another role
- **THEN** the backend treats that provider as primary for the first role and fallback for the other role
- **AND** role chains remain independent

#### Scenario: Single-provider setting remains compatible

- **WHEN** a role-specific provider-chain variable is not configured
- **THEN** provider construction builds a one-provider chain from the existing single-provider setting for that role
- **AND** existing `MODEL_PROVIDER`, `JUDGE_PROVIDER`, `SEARCH_PROVIDER`, and `VISION_PROVIDER` deployments remain valid

#### Scenario: Embeddings remain single provider

- **WHEN** embedding provider configuration is evaluated
- **THEN** the backend uses `EMBEDDING_PROVIDER` as a single provider selection
- **AND** no embedding provider fallback chain is constructed

### Requirement: Technical provider fallback

The backend SHALL fail over to the next configured provider in a role chain only for technical provider failures and SHALL NOT fail over for valid semantic decisions.

#### Scenario: Transient provider failure triggers fallback

- **WHEN** a provider call fails due to timeout, rate limit, service unavailable response, network failure, empty response, or another classified transient technical failure
- **THEN** the fallback wrapper attempts the next healthy configured provider for the same role and operation
- **AND** the caller receives the first successful provider result that satisfies the role interface

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

### Requirement: Provider attempt timeouts

The backend SHALL apply configurable per-role attempt timeouts to provider fallback calls.

#### Scenario: Provider attempt exceeds role timeout

- **WHEN** a provider attempt exceeds the configured timeout for its role
- **THEN** the attempt is classified as a timeout failure eligible for fallback
- **AND** the wrapper attempts the next healthy provider when one is available

#### Scenario: Role timeout unset

- **WHEN** a role-specific provider attempt timeout is not explicitly configured
- **THEN** the backend uses the documented default timeout for that role

### Requirement: Provider circuit breaker

The backend SHALL maintain a simple in-memory circuit breaker keyed by provider name, role, and operation so recently failing providers can be skipped temporarily.

#### Scenario: Circuit opens for transient failure

- **WHEN** a provider attempt fails due to a timeout, rate limit, or transient provider failure
- **THEN** the circuit breaker opens for that provider, role, and operation for the configured role duration
- **AND** the backend records the circuit-open event in logs and metrics

#### Scenario: Open circuit skips provider

- **WHEN** a provider, role, and operation circuit is open
- **THEN** the fallback wrapper skips that provider attempt and tries the next configured provider
- **AND** the backend records the skipped unhealthy provider in logs and metrics

#### Scenario: Non-transient failure does not open circuit

- **WHEN** a provider attempt fails due to non-transient configuration or validation setup error
- **THEN** the circuit breaker does not open for that provider solely because of that error

#### Scenario: Circuit breaker duration defaults

- **WHEN** a role-specific circuit breaker duration is not configured
- **THEN** the backend uses a 60 second open duration for that role

### Requirement: Provider chain construction failure handling

The backend SHALL handle non-transient provider configuration failures according to environment while preserving clear operational visibility.

#### Scenario: Development configuration failure is fatal

- **WHEN** the backend is running in a local or development environment
- **AND** a configured provider in a role chain has a non-transient configuration failure
- **THEN** provider construction fails clearly with the affected role and provider name

#### Scenario: Production configuration failure continues chain

- **WHEN** the backend is running in production
- **AND** a configured provider in a role chain has a non-transient configuration failure
- **THEN** provider construction or role resolution logs the failed provider clearly
- **AND** continues with remaining configured providers for that role when available

### Requirement: Provider fallback observability

The backend SHALL emit structured logs, Prometheus metrics, and diagnostics for provider fallback attempts without exposing secrets or raw provider payloads.

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

#### Scenario: Secrets are not logged

- **WHEN** provider fallback logs, metrics, or diagnostics are emitted
- **THEN** they exclude raw credentials, prompts, full model responses, and raw provider payloads
