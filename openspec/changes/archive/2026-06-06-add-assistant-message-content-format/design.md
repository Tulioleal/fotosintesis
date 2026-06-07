## Context

The assistant chat API returns `AssistantMessage` with `role` and `content`, and the frontend appends `response.message.content` directly into the chat transcript. Backend assistant persistence stores response metadata, but the message payload and metadata do not currently carry a declared content format. The grounded answer prompt focuses on evidence use and attribution, not on constraining the model away from Markdown.

The UI currently renders message content as React text rather than parsed Markdown, so Markdown syntax is visible to users. This change makes plain text the explicit current contract while reserving `markdown` as a future value that can be rendered later without another API shape change.

## Goals / Non-Goals

**Goals:**

- Expose `content_format` on assistant API messages with closed values `plain_text` and `markdown`.
- Default new assistant responses and persisted metadata to `plain_text`.
- Preserve backward compatibility by treating missing format values as `plain_text`.
- Instruct the model to produce plain text only and avoid Markdown, HTML, tables, code blocks, headings and bullet lists.
- Add a small frontend rendering boundary that preserves plain-text line breaks and falls back to raw text for `markdown` or unknown values.
- Regenerate frontend OpenAPI types from the backend schema.

**Non-Goals:**

- Rendering Markdown or installing a Markdown renderer.
- Rendering or allowing raw HTML.
- Sanitizing, stripping, rejecting or retrying model output that violates the prompt.
- Changing assistant response content to structured JSON.
- Changing source attribution rendering.
- Migrating existing persisted message metadata.
- Adding telemetry for model format violations.

## Decisions

- Represent message format as a closed schema enum, defaulting to `plain_text`.

  Rationale: an enum-compatible field gives backend, OpenAPI and generated frontend types the same contract. Defaulting at the schema boundary keeps callers and persisted older messages compatible.

  Alternative considered: keep `content: string` only and rely on prompt wording. This does not create a forward-compatible API contract for future Markdown rendering.

- Set assistant response metadata to include `content_format: "plain_text"` when saving new assistant messages.

  Rationale: persisted messages should retain the format in effect at creation time. Existing metadata can remain untouched because consumers default missing values to plain text.

  Alternative considered: database migration for existing metadata. This is unnecessary because missing format and `plain_text` have identical runtime behavior.

- Keep the frontend render boundary intentionally minimal.

  Rationale: the boundary centralizes future format branching while all current formats render as raw text. `white-space: pre-wrap` preserves model-intended line breaks without parsing Markdown.

  Alternative considered: add Markdown rendering immediately. This is explicitly out of scope and would introduce sanitization and dependency decisions not needed for the current UI.

- Enforce plain text through prompt instructions, not post-processing.

  Rationale: the project needs better model guidance without hiding or mutating model output. The UI still safely renders raw text, including accidental Markdown syntax.

  Alternative considered: sanitize or strip Markdown from output. This could damage legitimate botanical content and creates behavior beyond the requested contract.

## Risks / Trade-offs

- Model may still produce Markdown despite instructions -> The frontend renders raw text safely; tests cover prompt instructions rather than impossible model guarantees.
- Future Markdown support must revisit sanitization -> Reserving the enum value does not imply rendering; implementation remains plain-text fallback until a dedicated Markdown rendering change is proposed.
- Generated type drift could occur if OpenAPI artifacts are not regenerated -> Include type generation/update and frontend type-check/test verification in tasks.
- Unknown future format values may arrive before frontend support -> The render boundary treats unsupported values as plain text and does not throw.
