## Why

The MVP depends on external model, vision, search, embedding and judge providers, so domain logic must be isolated from provider SDKs before feature flows are built. Observability must also exist early because RAG, MaaS and agent behavior are hard to debug after the fact.

## What Changes

- Define provider interfaces for text generation, JSON generation, image analysis, embeddings and judge evaluation.
- Implement mock providers for model, vision identification, search and embeddings.
- Add provider configuration that avoids coupling domain logic to SDKs.
- Add structured JSON logging for requests, tool runs, provider calls and errors.
- Add health check and metrics endpoints.
- Add tracing hooks around chat, RAG, MaaS, GBIF and ingestion flows.

## Capabilities

### New Capabilities

- `provider-observability`: provider abstraction, mocks, health, metrics, logs and tracing.

### Modified Capabilities

- None.

## Impact

- Affects backend provider boundaries, configuration, request instrumentation and operational endpoints.
