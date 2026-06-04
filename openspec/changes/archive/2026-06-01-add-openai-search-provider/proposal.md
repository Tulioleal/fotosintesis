## Why

The backend already supports configurable OpenAI providers for model, vision, and judge roles, but search remains limited to the mock provider. Adding an OpenAI-backed web search provider enables production retrieval while preserving the existing provider configuration pattern and trusted-source filtering.

## What Changes

- Add configurable `SEARCH_PROVIDER=openai` support for web search.
- Add an `OpenAISearchProvider` that implements the existing `SearchProvider` interface and returns `SearchResult` values.
- Use the OpenAI Responses API web search tool through the existing async OpenAI helper and provider logging patterns.
- Add `openai_search_model`/`OPENAI_SEARCH_MODEL` configuration, consistent with the existing OpenAI model settings.
- Require `OPENAI_API_KEY` only when OpenAI search is selected.
- Preserve the existing `KnowledgeAcquisitionService` search call pattern and backend-side trusted-source validation.
- Add tests for provider selection, missing credentials, result parsing, and existing provider isolation behavior.

## Capabilities

### New Capabilities
- `openai-search-provider`: Configurable OpenAI-backed web search provider for knowledge acquisition search retrieval.

### Modified Capabilities
- `knowledge-rag-acquisition`: Search retrieval can use a configured OpenAI provider while preserving trusted-source filtering and the current acquisition flow.
- `provider-observability`: OpenAI search provider operations are logged and reported consistently with other configured providers.

## Impact

- Backend provider configuration in `backend/app/core/settings.py` and `backend/.env.example`.
- Provider factory wiring in `backend/app/providers/factory.py`.
- OpenAI provider implementations in `backend/app/providers/openai.py`.
- Existing search interfaces and result types in `backend/app/providers/interfaces.py` and `backend/app/providers/types.py` remain unchanged.
- Tests in `backend/tests/test_system_providers.py` and any focused OpenAI provider tests needed for result parsing.
