## Context

This slice depends on provider abstractions, knowledge retrieval and core domain services. It should orchestrate available capabilities through tools instead of duplicating their logic.

## Goals / Non-Goals

**Goals:**

- Deliver a user-facing chat flow.
- Ground botanical answers in retrieval when evidence exists.
- Use LangGraph for non-linear decisions, tools, clarification and failure handling.
- Protect against prompt injection and false action success claims.

**Non-Goals:**

- No new knowledge model beyond using the knowledge/RAG services.
- No standalone reminder or light meter UI beyond tool access.

## Decisions

- The graph includes intent classification, user context loading, retrieval, sufficiency evaluation, answer generation, clarification and failure paths.
- Tools wrap existing domain services: knowledge search, trusted search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup.
- The assistant asks clarifying questions when plant references are ambiguous.
- Tool failures are surfaced honestly to the user and logged.

## Risks / Trade-offs

- Agent complexity can grow quickly; keep nodes small and observable.
- Tool permissions must be strict to prevent prompt injection from triggering unsafe actions.
