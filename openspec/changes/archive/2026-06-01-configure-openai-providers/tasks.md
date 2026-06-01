## 1. Configuration

- [x] 1.1 Add per-role provider settings for model, vision, judge, search and embeddings with mock defaults.
- [x] 1.2 Add OpenAI credential and model-name settings for selected OpenAI-backed roles.
- [x] 1.3 Update backend and deployment environment examples with the new provider settings.

## 2. Provider Registry

- [x] 2.1 Extend `ProviderRegistry` with a dedicated judge provider role.
- [x] 2.2 Replace single-profile factory wiring with per-role provider construction.
- [x] 2.3 Ensure non-selected OpenAI roles do not require OpenAI credentials.
- [x] 2.4 Preserve mock providers as the default for all roles.

## 3. OpenAI Providers

- [x] 3.1 Add an OpenAI model provider implementing text and JSON generation interfaces.
- [x] 3.2 Add an OpenAI vision provider implementing the image analysis interface.
- [x] 3.3 Add an OpenAI judge provider implementing the judge evaluation interface.
- [x] 3.4 Map OpenAI responses into existing internal provider result types.
- [x] 3.5 Wrap OpenAI SDK calls with provider-call logging and tracing using sanitized metadata.

## 4. Evaluation Wiring

- [x] 4.1 Update evaluation runner setup to use the registry judge provider when no explicit judge provider is injected.
- [x] 4.2 Keep direct test injection of judge providers supported for deterministic evaluation tests.

## 5. Tests

- [x] 5.1 Add tests proving OpenAI model selection does not change configured search or embedding providers.
- [x] 5.2 Add tests proving OpenAI vision selection does not change the configured model provider.
- [x] 5.3 Add tests proving OpenAI judge selection does not change runtime generation provider wiring.
- [x] 5.4 Add tests for missing OpenAI credentials only failing selected OpenAI roles.
- [x] 5.5 Add tests confirming default local and CI configuration still uses deterministic mocks without OpenAI credentials.
