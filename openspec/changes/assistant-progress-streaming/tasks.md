## 1. Backend Event Contract

- [x] 1.1 Define closed event schemas: `stage` (id, Spanish label, index), terminal `result`, terminal `error`.
- [x] 1.2 Map graph nodes to stage ids; author Spanish labels server-side; forbid client-composed stage copy.
- [x] 1.3 Add async stage-emitter hook to assistant service/graph facade; blocking mode behaves identically to today.

## 2. Streaming Endpoint

- [x] 2.1 Implement the streaming chat endpoint emitting SSE frames, gated by feature flag.
- [x] 2.2 Emit heartbeat comment frames at fixed interval during silent stages; enforce duration bounds inherited from provider timeout settings.
- [x] 2.3 Guarantee exactly one terminal frame last, then close.
- [x] 2.4 Apply redaction whitelist in event builder; tests assert prompts/provider payloads/evidence bodies never serialize into frames.
- [x] 2.5 Propagate client disconnects; preserve existing persistence rules for aborted turns.

## 3. Frontend Transport

- [x] 3.1 BFF streaming route resolving backend auth headers server-side, piping SSE with buffering disabled; reject unauthenticated sessions with 401 before connecting.
- [x] 3.2 SSE consumer: parse stage/result/error frames, tolerate heartbeats, fall back to blocking POST on connect/parse/premature-close failure.
- [x] 3.3 Drive pending region from stage events using Notice primitive + aria-live queue; suppress rotating stopgap copy only while a stream is active.
- [x] 3.4 On terminal `result`, append message through existing rendering path; on terminal `error`, reuse retryable-failure UI without appending a bubble.

## 4. Degradation and Flags

- [x] 4.1 Wire feature flag so disabling removes the stream route server-side and forces blocking everywhere.
- [x] 4.2 Add Accept/capability negotiation or flag probe so older clients never receive SSE from the JSON endpoint.

## 5. Verification

- [x] 5.1 Unit-test ordering: monotonic stages, unique terminal, heartbeats present on slow stages, no post-terminal frames.
- [x] 5.2 Integration-test auth: unauthenticated stream rejected at BFF; cross-user isolation unchanged.
- [x] 5.3 Test degradation: forced stream failure yields identical conversation outcomes via blocking fallback.
- [x] 5.4 Vitest coverage: stage rendering, aria-live announcements, fallback switching.
- [x] 5.5 Backend + frontend lint/typecheck/tests green.
