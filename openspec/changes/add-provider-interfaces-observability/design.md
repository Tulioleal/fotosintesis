## Context

This change creates backend seams used by future slices. It should not implement real provider SDK integrations yet; mocks and interfaces are enough to unlock deterministic development and tests.

## Goals / Non-Goals

**Goals:**

- Keep MaaS, LLM, embeddings, search and judge providers replaceable.
- Support local development and tests without real credentials.
- Record enough operational data to debug provider and agent behavior.

**Non-Goals:**

- No production provider selection beyond configuration shape.
- No full assistant, RAG or plant identification flow.

## Decisions

- Domain services depend on internal interfaces, not provider SDK classes.
- Mocks are first-class providers for model, vision identification, search and embeddings.
- Logs are structured JSON and include request, provider, tool and error context.
- Health and metrics endpoints are implemented before feature endpoints depend on them.
- Tracing hooks are placed around planned chat, RAG, MaaS, GBIF and ingestion boundaries even if early implementations are mocked.

## Risks / Trade-offs

- Overly generic interfaces can hide provider-specific capabilities; keep them tailored to MVP use cases.
- Tracing must avoid leaking prompts, secrets or personal user data.
