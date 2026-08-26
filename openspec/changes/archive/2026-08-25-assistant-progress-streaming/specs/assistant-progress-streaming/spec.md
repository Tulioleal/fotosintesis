## ADDED Requirements
### Requirement: Server-authored progress event stream

The assistant SHALL offer a server-sent-events chat variant that streams bounded progress events during graph execution. Events SHALL use a closed vocabulary mapped to graph stages, SHALL carry server-authored Spanish labels, and SHALL terminate with exactly one terminal event containing either the full assistant chat response payload or the retryable error payload. Internal prompts, raw provider payloads, raw evidence bodies, and injection-defense internals MUST NOT be emitted as events.

#### Scenario: Stage transitions stream during a chat turn

- WHEN a client connects to the streaming chat endpoint and sends a message
- THEN the server emits ordered stage events corresponding to executed graph stages with their Spanish labels
- AND finishes with exactly one terminal `result` or `error` event and closes the stream

#### Scenario: Terminal payload matches the blocking contract

- WHEN a streamed turn completes successfully or fails retryably
- THEN the terminal event serializes the same response schema as the blocking chat endpoint for the same outcome
- AND no parallel or divergent response shape is introduced

#### Scenario: Internal content never streams

- WHEN any stage executes, including web fallback and safety handling
- THEN emitted events exclude prompts, raw provider requests or responses, raw retrieved evidence text, and injection-pattern internals

### Requirement: Ordered delivery with liveness bounds

Stage events SHALL arrive in monotonic execution order without repetition per request, with heartbeat frames during silent intervals and a bounded overall connection lifetime derived from existing provider timeout settings. No frames SHALL follow the terminal event.

#### Scenario: Slow stage emits heartbeats

- WHEN a stage runs longer than the heartbeat interval
- THEN the server emits heartbeat comment frames until the next stage or terminal event

#### Scenario: Connection closes at terminal

- WHEN the terminal event has been flushed
- THEN the server closes the connection
- AND no further events or frames are sent

### Requirement: Authenticated streaming through the BFF proxy

Streaming requests SHALL authenticate identically to the blocking chat route: the Next.js BFF route SHALL resolve backend auth headers server-side and forward them to the backend stream endpoint. Session credentials SHALL NOT appear in query strings or event payloads, and the streamed response SHALL disable intermediary buffering.

#### Scenario: Unauthenticated stream attempt

- WHEN an unauthenticated session requests the streaming route
- THEN the proxy rejects the request before contacting the backend stream

#### Scenario: Authenticated stream proxies cleanly

- WHEN an authenticated session opens the stream
- THEN the proxy forwards resolved auth headers, streams `text/event-stream` bytes without buffering, and preserves event order

### Requirement: Graceful degradation to blocking chat

The blocking JSON chat endpoint SHALL remain the canonical contract. Clients SHALL fall back to it when the stream is unavailable, fails mid-turn, or the feature flag is disabled, and the resulting conversation outcome SHALL be equivalent to a native blocking call. The client-side rotating pending copy SHALL remain the non-streaming treatment and SHALL be suppressed only while a live stage stream is active.

#### Scenario: Flag disabled

- WHEN streaming is disabled server-side
- THEN clients use the blocking chat endpoint with unchanged behavior

#### Scenario: Mid-turn stream failure falls back

- WHEN the stream connection breaks before a terminal event
- THEN the client retries via the blocking endpoint according to existing retryable-failure semantics
- AND conversation persistence follows the existing rules for the aborted attempt

### Requirement: Frontend renders server-authored stages

When a stage stream is active, the assistant pending state SHALL render the received stage labels and completion progress inside the established Fotosíntesis pending treatment, announce stage changes through the accessible live-region queue, and append the final message only from the terminal `result` event.

#### Scenario: Live stage updates replace static copy

- WHEN stage events arrive while the assistant is responding
- THEN the pending region reflects the current server-authored stage
- AND the rotating client-side stopgap copy is not shown simultaneously

#### Scenario: Accessible announcements

- WHEN a stage transition or terminal event arrives
- THEN the change is announced politely through the existing live-region announcer queue without moving focus
