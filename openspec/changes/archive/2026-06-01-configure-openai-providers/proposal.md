## Why

Fotosintesis needs OpenAI support without collapsing all AI responsibilities into a single global provider setting. Model generation, vision analysis and LLM-as-judge evaluation should be independently configurable, while search and embeddings remain separately configurable so retrieval and acquisition can keep their own provider choices.

## What Changes

- Add OpenAI-backed implementations for model generation, vision analysis and judge evaluation provider roles.
- Allow model, vision and judge providers to be configured independently, including independent provider name, model name and credential selection where applicable.
- Preserve separate configuration for search and embeddings so enabling OpenAI for generation or vision does not implicitly change retrieval, web search or embedding behavior.
- Keep domain services dependent on internal provider interfaces rather than OpenAI SDK types.
- Maintain deterministic mock behavior for local and CI runs without real OpenAI credentials.
- Extend provider observability so OpenAI calls are logged, traced and measured with the same sanitized provider-call metadata as other providers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `provider-observability`: Provider configuration requirements will explicitly cover independently configurable OpenAI model, vision and judge providers while keeping search and embeddings separately configurable.

## Impact

- Backend provider configuration and dependency wiring.
- Internal model, vision and judge provider implementations.
- Evaluation runner judge-provider selection.
- Tests and mock provider configuration for local and CI execution.
- Structured provider-call logs, metrics and traces for OpenAI-backed operations.
