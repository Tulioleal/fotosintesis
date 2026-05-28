## Why

The assistant is the core generative experience of the MVP. It needs a RAG-grounded, tool-aware agent that can answer botanical questions, use user context and avoid claiming actions that failed.

## What Changes

- Implement chat API and frontend conversation UI.
- Implement LangGraph nodes for intent classification, context loading, retrieval, sufficiency evaluation, answer generation, clarification and failure handling.
- Add tools for knowledge search, trusted web search, taxonomy validation, ingestion, embeddings, garden lookup, reminder creation and light measurement lookup.
- Implement RAG-grounded botanical answers with uncertainty handling.
- Implement ambiguity handling for unspecified plants.
- Implement out-of-domain response behavior.
- Implement prompt-injection resistance and tool-use restrictions.
- Implement assistant-triggered reminder creation with confirmation when data is missing.
- Implement tool failure handling so the assistant never claims failed actions were completed.

## Capabilities

### New Capabilities

- `assistant-agent`: chat UI/API, LangGraph agent, RAG answers, tools, safety and failure handling.

### Modified Capabilities

- None.

## Impact

- Affects backend chat orchestration, frontend conversation UI, tool services, RAG usage, safety policies and conversation persistence.
