## Context

The current assistant plant-care path combines local RAG retrieval, structured plant-data lookup, trusted web fallback, multiple answerability checks, deterministic aspect validation, answer generation, and best-effort ingestion before the chat request completes. That path protects against unsupported answers, but it also adds latency and makes non-perfect evidence states hard to express to the user.

This design keeps the core safety goals: confirmed taxonomy gates evidence operations, answerability remains mandatory, sources remain visible, and unsupported facts are not persisted. It changes the orchestration so the user-facing answer path is shorter and the evidence status is explicit.

## Goals / Non-Goals

**Goals:**

- Use local RAG first when it fully answers the exact question.
- Improve RAG recall with a query that includes confirmed taxonomy, topic, required aspects, and the original user question.
- Search the web immediately when RAG is `partial`, `insufficient`, or `contradictory`.
- Evaluate RAG and web evidence with one final combined semantic judge before final answer synthesis.
- Generate transparent answers for `full`, `partial`, `insufficient`, and `contradictory` evidence states.
- Persist only judge-supported source claims, after response preparation, with a dedicated database session.

**Non-Goals:**

- Do not remove RAG, answerability judging, embeddings, or existing structured plant-data services from the backend.
- Do not introduce Celery, RQ, a persistent job table, or another full queue system in this iteration.
- Do not add database migrations.
- Do not persist final assistant responses, full pages by default, contradictory evidence, insufficient evidence, or general LLM guidance.
- Do not redesign the whole care-topic taxonomy beyond adding the taxonomy topic needed for native-range questions.

## Decisions

### Evidence status replaces boolean-only routing

The answerability contract will support `full`, `partial`, `insufficient`, and `contradictory` statuses. The existing `answerable` field remains for compatibility, but graph routing uses `status`.

Alternatives considered:

- Keep boolean answerability only. This is simpler but cannot distinguish partial, missing, and conflicting evidence well enough for transparent answers.
- Add separate booleans for each state. This creates invalid combinations; a single closed status is easier to validate.

### RAG query construction is enriched before retrieval

The retrieval query will include confirmed taxonomy, classified topic, required aspects, and the original user question. Topic remains available as a metadata filter, but the text query is no longer only species plus topic.

Alternatives considered:

- Keep the current query shape. This preserves behavior but misses specific user intent such as toxicity, pets, native range, or phrasing in Spanish.
- Use only the raw user question. This can lose the confirmed taxonomy and canonical aspect terms that help retrieval.

### Non-full RAG routes directly to web search

When RAG status is not `full`, the assistant searches the web before final answer synthesis. `partial` RAG still searches because web evidence can upgrade the answer from partial to full.

Alternatives considered:

- Answer partial RAG immediately. This reduces network calls but prevents a complete answer when live sources can fill missing aspects.
- Keep structured API lookup before web. Existing behavior shows the structured sources often add latency without answering exact user questions.

### Structured plant-data lookup is removed from normal chat-time care routing

Trefle/Perenual providers and `plant_data_lookup` remain available in the backend, but the normal assistant plant-care answer graph does not call them between RAG and web search.

Alternatives considered:

- Delete structured lookup entirely. This is unnecessary and would remove a useful backend capability for future offline ingestion.
- Keep lookup but make it optional. This preserves latency and routing ambiguity in the chat path.

### One final combined judge validates RAG and web evidence

The final judge receives the question, confirmed taxonomy, topic, required aspects, RAG chunks, RAG judge result, fetched web evidence, URLs, and metadata. It emits the final status, covered aspects, missing aspects, source support, contradictions, and confidence.

Alternatives considered:

- Judge each web source independently. This produces more calls and can miss cross-source contradictions.
- Trust search snippets directly. This is faster but weakens source support and persistence safety.

### Deterministic keyword validation stops blocking evidence

Semantic judging becomes the authority for aspect coverage. The implementation still validates the judge output structurally: required fields must be coherent with the status, source-supported claims are required for persistence, and incoherent outputs degrade to safer statuses.

Alternatives considered:

- Keep keyword gates after semantic judging. This is brittle across languages, synonyms, scientific phrasing, and spelling variants.
- Trust judge output without validation. This risks persisting malformed or unsupported claims.

### Answer synthesis separates verified evidence from general guidance

One answer prompt will be parameterized by final evidence status. Verified source-supported claims and conservative general guidance must be separate. General guidance can appear for partial, insufficient, and contradictory states only when clearly labeled as not source-validated for the specific plant/question.

Alternatives considered:

- Forbid all guidance when evidence is incomplete. This is safest but often unhelpful for users.
- Allow general guidance without labeling. This risks blending unsupported advice with verified evidence.

### Background ingestion is scheduled by AssistantService.chat

The graph returns answer text, sources, metadata, and a small ingestion payload. `AssistantService.chat` prepares and saves the user-facing response, then schedules background ingestion. The background function receives only serializable payload data, opens its own `AsyncSessionLocal` session, commits or rolls back its own transaction, and logs failures with conversation and plant context.

Alternatives considered:

- Await ingestion inside the graph. This is simpler but blocks the user.
- Use request-session objects inside `asyncio.create_task`. This is fragile because the request session may be closed or rolled back.
- Build a full queue and worker now. This is stronger long-term but too large for this iteration.

## Risks / Trade-offs

- Final judge quality becomes more important -> Mitigate with closed schemas, structural validation, status degradation, and no persistence on incoherent output.
- Partial/general guidance can blur with source-backed claims -> Mitigate by prompt constraints, response metadata, source citation boundaries, and persistence filtering.
- Background ingestion can fail after the user receives an answer -> Mitigate with dedicated sessions, explicit exception logging, and non-blocking failure metadata where available.
- Without a durable queue, scheduled ingestion can be lost if the process exits -> Accept for this iteration; the change intentionally avoids a full worker system.
- Removing structured lookup from chat can reduce coverage for some questions -> Mitigate by moving web search earlier and keeping structured providers for future offline ingestion.
- One combined judge may have larger prompts -> Mitigate by fetching at most three usable web sources and passing bounded evidence excerpts.

## Migration Plan

1. Extend care contracts and parsing to support explicit answerability status while preserving `answerable` for compatibility.
2. Add `CareTopic.taxonomy` and map native-range required aspects to it.
3. Change RAG query construction to include taxonomy, topic, required aspects, and user question.
4. Update graph routing to skip structured lookup in the normal chat-time plant-care path and route non-full RAG to web search.
5. Replace per-source web validation with the final combined judge and structural validation.
6. Update answer synthesis prompts and metadata for the four evidence statuses.
7. Move validated web-claim ingestion scheduling to `AssistantService.chat` with a dedicated background session.
8. Update tests for routing, answer policy, persistence filtering, and background ingestion session isolation.

Rollback is code-only: restore the previous graph routing and disable background ingestion scheduling. No database rollback is required because this change does not add migrations.

## Open Questions

- Whether the first background ingestion implementation should expose failed ingestion status in response metadata, logs only, or both.
- Whether partial source-supported claims from external fallback sources should use a lower default confidence than trusted-domain claims in this iteration.
