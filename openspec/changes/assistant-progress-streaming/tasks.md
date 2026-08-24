## 1. Backend Event Contract

- [ ] 1.1 Define closed event schemas: `stage` (id, Spanish label, index), terminal `result`, terminal `error`.
- [ ] 1.2 Map graph nodes to stage ids; author Spanish labels server-side; forbid client-composed stage copy.
- [ ] 1.3 Add async stage-emitter hook to assistant service/graph facade; blocking mode behaves identically to today.

## 2. Streaming Endpoint

- [ ] 2.1 Implement the streaming chat endpoint emitting SSE frames, gated by feature flag.
- [ ] 2.2 Emit heartbeat comment frames at fixed interval during silent stages; enforce duration bounds inherited from provider timeout settings.
- [ ] 2.3 Guarantee exactly one terminal frame last, then close.
- [ ] 2.4 Apply redaction whitelist in event builder; tests assert prompts/provider payloads/evidence bodies never serialize into frames.
- [ ] 2.5 Propagate client disconnects; preserve existing persistence rules for aborted turns.

## 3. Frontend Transport

- [ ] 3.1 BFF streaming route resolving backend auth headers server-side, piping SSE with buffering disabled; reject unauthenticated sessions with 401 before connecting.
- [ ] 3.2 SSE consumer: parse stage/result/error frames, tolerate heartbeats, fall back to blocking POST on connect/parse/premature-close failure.
- [ ] 3.3 Drive pending region from stage events using Notice primitive + aria-live queue; suppress rotating stopgap copy only while a stream is active.
- [ ] 3.4 On terminal `result`, append message through existing rendering path; on terminal `error`, reuse retryable-failure UI without appending a bubble.

## 4. Degradation and Flags

- [ ] 4.1 Wire feature flag so disabling removes the stream route server-side and forces blocking everywhere.
- [ ] 4.2 Add Accept/capability negotiation or flag probe so older clients never receive SSE from the JSON endpoint.

## 5. Verification

- [ ] 5.1 Unit-test ordering: monotonic stages, unique terminal, heartbeats present on slow stages, no post-terminal frames.
- [ ] 5.2 Integration-test auth: unauthenticated stream rejected at BFF; cross-user isolation unchanged.
- [ ] 5.3 Test degradation: forced stream failure yields identical conversation outcomes via blocking fallback.
- [ ] 5.4 Vitest coverage: stage rendering, aria-live announcements, fallback switching.
- [ ] 5.5 Backend + frontend lint/typecheck/tests green.
