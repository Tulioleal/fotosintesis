## Context

The assistant graph currently retrieves botanical evidence through `knowledge_search`, evaluates chunk sufficiency, and routes insufficient evidence to clarification/limitation handling. `AssistantTools` already exposes `trusted_web_search`, and the provider registry can use OpenAI-backed web search when `SEARCH_PROVIDER=openai`, but the graph does not call that tool as a fallback.

Knowledge acquisition already persists trusted generated documents through `KnowledgeVectorIndex.ingest_document(...)`, which chunks, embeds, stores and indexes evidence. The fallback should reuse that path instead of introducing a separate embedding or persistence mechanism.

## Goals / Non-Goals

**Goals:**

- Run trusted web search when RAG retrieval is insufficient for a botanical answer.
- Answer from web-search snippets when available, while clearly identifying them as live web evidence rather than reviewed persisted knowledge.
- Include web-search results in assistant response sources.
- Persist and embed fallback web evidence through existing knowledge ingestion on a best-effort basis.
- Preserve degraded limitation/manual-search handling when fallback search fails or returns no usable results.

**Non-Goals:**

- Do not add a new search provider or external dependency.
- Do not relax trusted-source validation rules in knowledge acquisition.
- Do not implement true post-response background ingestion in this change.
- Do not change frontend API shapes beyond using existing `sources` and `tool_failures` metadata.

## Decisions

1. Add a `fallback_web_search` graph node after sufficiency evaluation.

   Rationale: This keeps the fallback explicitly tied to insufficient evidence and avoids changing the primary RAG retrieval path. The node can return either web results for answer generation or no answerable evidence, preserving existing clarify behavior.

   Alternative considered: Make `KnowledgeAcquisitionService.retrieve_or_acquire()` return raw web-search snippets when ingestion degrades. That would blur the line between persisted acquisition results and transient assistant fallback evidence.

2. Store fallback search results separately from RAG chunks.

   Rationale: `web_results` in `AssistantState` lets `generate_answer` prefer persisted RAG chunks when sufficient and only use live web snippets when no sufficient chunks exist. It also keeps source mapping straightforward.

   Alternative considered: Convert search results directly into synthetic `KnowledgeChunk` objects before answer generation. That risks making transient live evidence look like persisted RAG evidence.

3. Generate fallback answers from snippets and source metadata without additional model calls.

   Rationale: The current assistant answer generation is deterministic and evidence-extractive. Keeping fallback generation extractive minimizes cost and avoids unsupported synthesis from partial snippets.

   Alternative considered: Ask the model provider to synthesize a richer answer from search snippets. That may be useful later, but requires additional prompt and grounding tests.

4. Add best-effort persistence through an assistant tool method.

   Rationale: `AssistantTools` already owns provider access and the knowledge repository. A method such as `ingest_web_evidence(...)` can build a `KnowledgeDocumentInput` from trusted search results and call `KnowledgeVectorIndex.ingest_document(...)` with the configured embedding provider. Failures should be recorded but must not block returning the web answer.

   Alternative considered: Persist directly inside `AssistantGraph`. That would couple graph orchestration to repository/vector-index internals and make tests more brittle.

5. Persist before returning the final state, not after HTTP response completion.

   Rationale: A true post-response background task requires service/API-level changes and lifecycle/error handling. This change keeps implementation minimal and deterministic: generate the answer, attempt persistence, and return the answer even if persistence fails.

   Alternative considered: FastAPI `BackgroundTasks` ingestion. That is a larger cross-layer change and can be proposed separately if response latency becomes an issue.

## Risks / Trade-offs

- Web-search snippets may be incomplete or stale -> The answer must label them as live web evidence and cite source URLs.
- Persistence may fail because LlamaIndex, pgvector or embeddings are unavailable -> Treat ingestion as best-effort and keep the user-facing answer.
- Fallback search may add latency -> Only run it after insufficient RAG evidence, and keep the primary retrieved-evidence path unchanged.
- Mock search may make tests pass without validating OpenAI behavior -> Unit tests should assert tool calls and routing; existing provider tests cover OpenAI search mapping.
