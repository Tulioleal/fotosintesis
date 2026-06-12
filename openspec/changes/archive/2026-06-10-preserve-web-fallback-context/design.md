## Context

The assistant graph falls back from insufficient persisted RAG and structured plant-data evidence to trusted web search. The current fallback query combines the operational scientific name with the classified topic, but unsupported botanical questions often classify as generic `care`, dropping important user intent terms such as pet safety or native range. The same node records `web_search_used` before calling the tool, but the failure return path only returns `tool_failures`, so downstream diagnostics do not preserve that the web fallback route was attempted.

## Goals / Non-Goals

**Goals:**

- Preserve the user question context in trusted web fallback queries while still anchoring the query to the operational scientific name.
- Cap the user question portion of the search query to avoid sending unbounded text to the search provider.
- Preserve `web_search_used` in `fallback_reasons` even when trusted web search fails.
- Cover the behavior with focused assistant-agent tests for query content and failure metadata.

**Non-Goals:**

- Change intent classification or `_topic_for_message()` behavior.
- Change trusted search provider ranking, allowed-domain filtering, page fetching, ingestion, or answer synthesis.
- Add new API fields or alter persisted conversation data.

## Decisions

- Use the original assistant state message as the trusted web query context, capped with the existing `_shorten()` helper. This keeps exact terms the user asked about and avoids expanding topic-classification rules for every unsupported botanical intent.
- Keep the operational scientific name at the front of the query. This preserves plant specificity and avoids broad searches driven only by user wording such as "mascotas" or "nativa".
- Replace the generic `botanical care trusted source` suffix with `botanical trusted source`. The original question already supplies the specific subject, so retaining `care` would reintroduce generic bias for non-care questions.
- Return `fallback_reasons` from the trusted web search failure branch using the already-computed `fallback_reasons` list. This is the smallest change and keeps the same de-duplication behavior as successful and no-result fallback paths.

## Risks / Trade-offs

- User wording in the query may include extra conversational text -> mitigate by capping the message context and anchoring with scientific name plus trusted botanical terms.
- Exact query assertions may be sensitive to punctuation or cap length -> mitigate by asserting critical preserved terms for unsupported intents and one representative exact query for existing degraded knowledge behavior.
- Search quality may vary by language because user questions are preserved verbatim -> this is preferable to losing intent entirely, and existing provider behavior still filters to trusted sources.
