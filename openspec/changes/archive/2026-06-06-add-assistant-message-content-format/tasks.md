## 1. Backend Contract and Persistence

- [x] 1.1 Add a closed assistant message content format type in `backend/app/assistant/schemas.py` with values `plain_text` and `markdown`, defaulting `AssistantMessage.content_format` to `plain_text`.
- [x] 1.2 Update assistant response construction in `backend/app/assistant/service.py` so generated assistant messages return `content_format: "plain_text"`.
- [x] 1.3 Persist `content_format: "plain_text"` in assistant message metadata when saving new assistant responses, without migrating existing metadata.
- [x] 1.4 Ensure any backend code that reads assistant message metadata treats a missing `content_format` as `plain_text`.

## 2. Model Prompt

- [x] 2.1 Update `_grounded_answer_prompt` in `backend/app/assistant/graph.py` to instruct the model to output plain text only.
- [x] 2.2 Add explicit prompt prohibitions for Markdown, HTML, tables, code blocks, headings and bullet lists.

## 3. API Schema and Frontend Types

- [x] 3.1 Regenerate the OpenAPI TypeScript artifacts so `frontend/src/lib/generated/openapi.d.ts` includes `AssistantMessage.content_format` with `plain_text` and `markdown` values.
- [x] 3.2 Update frontend assistant chat types to consume the generated assistant message content format field without introducing a manually divergent response shape.

## 4. Frontend Rendering

- [x] 4.1 Add a minimal `AssistantMessageContent` render boundary that accepts `content` and optional `content_format`.
- [x] 4.2 Route assistant chat bubble rendering through `AssistantMessageContent` in `frontend/src/components/assistant/AssistantChat.tsx`.
- [x] 4.3 Render `plain_text`, missing formats, `markdown` and unsupported formats as raw React text without Markdown parsing.
- [x] 4.4 Preserve plain-text line breaks in assistant message bubbles with `white-space: pre-wrap` or equivalent styling.

## 5. Tests and Verification

- [x] 5.1 Add backend tests asserting generated assistant responses include `content_format: "plain_text"` and persisted metadata includes the same value.
- [x] 5.2 Add backend tests asserting `_grounded_answer_prompt` requires plain text and forbids Markdown, HTML, tables, code blocks, headings and bullet lists.
- [x] 5.3 Add frontend tests for `AssistantMessageContent` or assistant chat rendering that verify newline preservation behavior.
- [x] 5.4 Add frontend tests that verify `content_format: "markdown"` renders raw text, does not parse Markdown and does not throw.
- [x] 5.5 Run the relevant backend tests, frontend tests and type checks for the assistant/OpenAPI paths.
