## 1. Assistant Model Synthesis

- [x] 1.1 Add an assistant tool wrapper for configured model text generation with `ToolResult` error handling.
- [x] 1.2 Add a shared grounded answer synthesis helper that accepts user message, plant name, topic, evidence type, evidence text, limitations and source/provider metadata.
- [x] 1.3 Build a prompt that requires Spanish botanical answers grounded only in supplied evidence with explicit uncertainty when evidence is incomplete or degraded.
- [x] 1.4 Update sufficient RAG answer generation to attempt model-backed synthesis before deterministic fallback.
- [x] 1.5 Update sufficient structured plant-data answer generation to attempt model-backed synthesis before deterministic fallback.
- [x] 1.6 Update trusted web fallback answer generation to attempt model-backed synthesis before deterministic fallback and preserve existing ingestion behavior.

## 2. Safety And Fallback Handling

- [x] 2.1 Keep unsafe, out-of-domain, ambiguous, reminder and light-measurement flows deterministic and outside final answer synthesis.
- [x] 2.2 Record model generation failures as non-blocking tool failures without removing existing evidence sources from the response.
- [x] 2.3 Preserve deterministic summary builders for RAG, structured plant-data and trusted web evidence fallback responses.
- [x] 2.4 Ensure model synthesis does not change graph routing, plant confirmation gates, retrieval sufficiency checks or tool execution order.

## 3. Regression Tests

- [x] 3.1 Extend assistant fake tools or providers to capture model generation calls and returned text.
- [x] 3.2 Add tests proving sufficient RAG evidence invokes model-backed synthesis and preserves sources.
- [x] 3.3 Add tests proving structured plant-data evidence invokes model-backed synthesis with provider metadata.
- [x] 3.4 Add tests proving trusted web fallback invokes model-backed synthesis with source metadata and still performs best-effort ingestion.
- [x] 3.5 Add tests proving model generation failure returns deterministic evidence summaries and records a non-blocking tool failure.
- [x] 3.6 Add tests proving unsafe, out-of-domain, ambiguous and action flows do not invoke model-backed synthesis unnecessarily.

## 4. Verification

- [x] 4.1 Run backend assistant tests.
- [x] 4.2 Run provider or configuration tests if model/provider wiring is changed.
- [x] 4.3 Run OpenSpec status or validation for `use-model-for-assistant-answer-synthesis`.
