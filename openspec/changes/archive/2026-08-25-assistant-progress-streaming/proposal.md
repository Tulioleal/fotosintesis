## Why

A chat turn is a single blocking POST that can run classification, context loading, retrieval, answerability judging, web fallback, and generation. Users see only a static line ("Consultando fuentes y herramientas...") for the entire duration, and a client-side rotating fake-stage stopgap is being shipped separately to mask the silence. The graph already has well-defined stages; the transport simply never exposes them. Progress must become real, server-authored, and bounded — without leaking internals.

## What Changes

- Add a server-sent-events chat variant that streams typed stage-transition events during graph execution and terminates with one event carrying the complete `AssistantChatResponse` payload (or the retryable-error payload).
- Author stage copy server-side in Spanish from a closed stage vocabulary mapped to graph nodes (`classify_intent`, `load_user_context`, `retrieve`, `evaluate_sufficiency`, `fallback_web_search`, `generate_answer`, clarify/action/failure states); clients render, never compose.
- Carry the SSE stream through the Next.js BFF proxy with session-resolved auth headers; no tokens in query strings.
- Guarantee event ordering: monotonic stage sequence, exactly one terminal event (`result` or `error`), heartbeats during long stages, connection close at terminal.
- Preserve graceful degradation: blocking JSON `POST /assistant/chat` remains fully functional and is the fallback when streaming is unavailable (feature flag).
- Define non-streamable content: internal prompts, raw provider payloads, raw evidence bodies, and injection-check details are never emitted as events.
- Supersede the client-side rotating fake-stage copy when streaming is active, without removing it for non-streaming fallbacks.

## Capabilities

### New Capabilities

- `assistant-progress-streaming`: Server-authored progress events for assistant chat execution over SSE.

### Modified Capabilities

- `assistant-agent`: Chat experience gains a streaming transport variant beside the blocking JSON contract.
- `frontend-visual-system`: Assistant experience renders live server-authored stages in the established Fotosíntesis pending treatment when streaming is available.

## Impact

- Backend: streaming chat endpoint (FastAPI streaming response emitting SSE frames), stage-emission hook in the assistant service/graph facade, event schemas, feature-flag setting.
- Frontend: BFF passthrough streaming route handler, SSE consumer with fallback to the blocking call, pending-state rendering driven by stage events, aria-live announcements reusing the announcer queue pattern.
- Contracts: event type definitions shared via generated types; retryable-error semantics reused from `AssistantRetryableError`.
- Tests: event order, terminal uniqueness, heartbeat presence, auth rejection, degradation path, redaction assertions.
