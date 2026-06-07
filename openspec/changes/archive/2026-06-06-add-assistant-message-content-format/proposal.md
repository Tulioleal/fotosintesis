## Why

Assistant responses are currently rendered as raw React text, while the backend prompt and API contract do not explicitly declare that the content is plain text. When model output includes Markdown syntax, the chat UI can display formatting artifacts poorly and there is no stable contract for adding Markdown rendering later.

## What Changes

- Add an explicit assistant message content format contract using closed values `plain_text` and `markdown`.
- Default all newly emitted assistant messages to `content_format: "plain_text"` in API responses and persisted message metadata.
- Treat missing `content_format` values as `plain_text` so existing messages remain compatible without a database migration.
- Update assistant answer synthesis prompting to require plain-text output and forbid Markdown, HTML, tables, code blocks, headings and bullet lists.
- Route frontend assistant message rendering through a minimal format-aware boundary that preserves plain-text line breaks and silently falls back to raw text for `markdown` or unsupported formats.
- Update OpenAPI schema generation and frontend generated types so `AssistantMessage` exposes the content format field without manual type divergence.

## Capabilities

### New Capabilities

### Modified Capabilities

- `assistant-agent`: Adds the assistant message content format contract, plain-text model prompt requirements, backend persistence defaults and frontend format-aware rendering behavior.
- `openapi-typescript-client`: Adds generated frontend contract coverage for the assistant message `content_format` enum-compatible field.

## Impact

- Backend assistant response schemas, service response construction, message metadata persistence and grounded-answer prompt text.
- Assistant chat API OpenAPI schema and generated frontend TypeScript contracts.
- Frontend assistant chat rendering components and styles.
- Backend and frontend tests covering content format defaults, metadata persistence, prompt instructions, newline preservation and fallback rendering.
- No Markdown renderer, HTML rendering, sanitization, model-output rejection, telemetry or database migration is introduced.
