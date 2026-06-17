## Why

The assistant currently falls back to deterministic classification when the LLM classifier returns a structurally incomplete response, such as omitting `confidence`, even though the intended classification may be otherwise valid. This creates avoidable deterministic routing, misleading `tool_failures`, and less reliable multilingual intent handling.

## What Changes

- Strengthen the assistant classifier structured-output contract so required classifier fields, including `confidence`, are explicitly required by the provider schema.
- Add one structured-output repair retry before falling back to deterministic classification for recoverable classifier validation errors.
- Stop treating low classifier confidence as an automatic reason to discard otherwise valid LLM classifications.
- Keep classifier confidence as observability metadata and diagnostic signal rather than a hard trust gate.
- Preserve deterministic fallback for true classifier unavailability, timeout, unrecoverable provider errors, and invalid output after retry.
- Adjust tests to cover stricter schema requirements, retry behavior, and low-confidence LLM classification acceptance.

## Capabilities

### New Capabilities

### Modified Capabilities

- `assistant-agent`: Change classifier fallback behavior so valid LLM classifications are preferred, low confidence is diagnostic-only, and deterministic routing is reserved for unavailable or structurally unusable classifier output after retry.

## Impact

- Affected backend code: `backend/app/assistant/graph.py`, classifier schema/prompt/retry logic, and classifier fallback metadata handling.
- Affected tests: assistant-agent tests for classifier fallback, low-confidence classification, invalid classifier output, and schema requirements.
- No public API shape change is expected; response diagnostics and `tool_failures` should become less noisy for recoverable classifier behavior.
- No new external dependencies are expected.
