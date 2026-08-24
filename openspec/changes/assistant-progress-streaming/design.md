## Context

Chat is one blocking call: `frontend/src/app/api/assistant/chat/route.ts` proxies to backend `/assistant/chat` -> `AssistantService.chat`. No SSE/WebSocket exists anywhere. Graph topology defines discrete stages (`classify_intent` -> `load_user_context` -> `retrieve` -> `evaluate_sufficiency` -> `fallback_web_search` -> `generate_answer`, plus clarify/handle_action/failure). The frontend currently shows a static pending line, with a rotating fake-stage stopgap already landed as a stopgap. Frontend primitives exist for announcement patterns (Notice, aria-live region, enrichment announcer queue).

## Goals / Non-Goals

**Goals:**

- Real, server-authored stage visibility with bounded, safe event content.
- One terminal event carrying the exact existing response contract — no parallel response shape.
- Zero regression for blocking clients; streaming is additive.

**Non-Goals:**

- No token-by-token answer streaming; only stage transitions and the terminal payload.
- No WebSocket infrastructure; SSE only.
- No removal of the blocking endpoint or the fake-stage stopgap for non-streaming clients.
- No new provider instrumentation beyond existing stage boundaries.

## Decisions

- **SSE over POST, plain generator first.** FastAPI `StreamingResponse` with a hand-rolled SSE frame encoder; adopt `sse-starlette` only if reconnect/Last-Event-ID handling is needed. A dedicated `POST /assistant/chat/stream` avoids content-negotiation ambiguity and keeps the blocking contract untouched.
- **Closed event vocabulary.** Events: `stage {stage_id, label_es, index}`, heartbeat comment frames, terminal `result {...AssistantChatResponse}`, terminal `error {...retryable failure}`. Stage ids map 1:1 to graph node names plus action/clarify/failure; Spanish labels live server-side as the single source of truth.
- **Emission hook, not graph rewrite.** The graph facade publishes stage transitions through an async callback consumed by the stream generator; blocking mode ignores the callback. No topology changes.
- **Terminal payload equals existing contract.** Consumers need one parser; no divergent response shape.
- **Auth and proxy.** BFF stream route resolves backend auth headers server-side (same as blocking route) and pipes bytes verbatim with `text/event-stream`; buffering disabled via response headers; credentials never touch query strings.
- **Liveness bounds.** Heartbeats at fixed interval during silent stages; overall duration bounded by existing provider timeouts/judge limits; connection always closes after the terminal event.
- **Ordering guarantees.** Stages monotonic non-repeating per request; exactly one terminal frame last; nothing after it.
- **Redaction boundary.** Event builder whitelists fields; prompts, provider payloads, raw evidence text, and injection internals are structurally absent, not merely filtered at render time.
- **Degradation.** Feature flag disables streaming server-side; frontend tries stream then falls back to blocking on connect/parse/premature-close failure; rotating stopgap copy remains the non-streaming pending treatment.

## Risks / Trade-offs

- Proxy/CDN buffering breaks SSE → disable buffering explicitly on both hops; verify in deployed environment early.
- Duplicated execution paths drift → single service method parameterized by an optional emitter; blocking mode is emitter-less streaming.
- Long-lived connections hold DB sessions → stream lifecycle wraps the same request scope; terminal flush precedes session close.
- Stage spam on fast turns → coalesce sub-threshold stages; near-immediate terminal allowed for fast answers.
- Client aborts mid-stream → cancellation propagates through the generator; partial turns follow existing persistence rules.

## Migration Plan

1. Emitter hook + event schemas + stream endpoint behind disabled flag; unit-test event sequences from the facade.
2. BFF streaming proxy; frontend consumer with automatic fallback; render stages in existing pending region.
3. Enable flag; observe; retire nothing — blocking path and stopgap copy remain.
4. Rollback: flip flag off; frontend falls back automatically.

## Open Questions

- Dedicated `POST /assistant/chat/stream` endpoint vs content negotiation on the existing `POST /chat`?
- Hand-rolled SSE frames vs adopting `sse-starlette` (reconnect/Last-Event-ID support)?
- Heartbeat cadence, and whether stage events should coalesce below a minimum inter-event gap?
