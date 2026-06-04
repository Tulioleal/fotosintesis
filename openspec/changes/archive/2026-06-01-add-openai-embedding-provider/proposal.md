## Why

Embeddings are already a first-class provider role in the backend, but they can only use deterministic mocks while model, vision and judge roles can be configured independently with OpenAI. Supporting `EMBEDDING_PROVIDER=openai` closes that provider parity gap for RAG ingestion, retrieval and assistant embedding tools without coupling embeddings to any other OpenAI-backed role.

## What Changes

- Add OpenAI-backed embedding provider configuration through `EMBEDDING_PROVIDER=openai`.
- Add an `OPENAI_EMBEDDING_MODEL` setting and document it in backend and deployment environment examples.
- Implement an `OpenAIEmbeddingProvider` behind the existing `EmbeddingProvider.create_embeddings()` interface.
- Wire embedding provider construction through the existing provider registry with role-specific OpenAI credential validation.
- Preserve mock embeddings as the default for local and CI runs.
- Keep model, vision, judge, search and embedding provider selections independent.
- Extend provider observability requirements so OpenAI embedding calls emit sanitized provider-call telemetry like other OpenAI roles.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `provider-observability`: OpenAI-backed role providers and provider-call observability now include embeddings alongside model, vision and judge roles.

## Impact

- Backend settings and environment examples gain `OPENAI_EMBEDDING_MODEL`.
- Provider factory wiring gains OpenAI embedding construction and role-specific credential checks.
- `app.providers.openai` gains an embedding provider implementation using the OpenAI SDK.
- RAG ingestion, knowledge acquisition, assistant embedding tool calls and `/health` provider reporting can operate with either mock or OpenAI embeddings through the existing interface.
- Tests cover independent provider selection, missing credentials, response mapping, observability and unchanged mock defaults.
