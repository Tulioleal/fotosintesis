## Context

The existing knowledge acquisition path uses `TrustedSourceValidator` to restrict persistent knowledge ingestion to approved HTTPS domains with matching source metadata. Assistant fallback persistence currently builds and ingests a `KnowledgeDocumentInput` from every usable fallback `SearchResult`, and fallback search does not pass configured trusted domains to the search provider.

The fix should preserve the assistant's degraded-answer behavior while closing the persistence gap: live fallback answers can still proceed when usable evidence exists, but only trusted results may be persisted or indexed as knowledge.

## Goals / Non-Goals

**Goals:**

- Reuse the existing trusted-source validation rules for assistant fallback evidence persistence.
- Avoid persisting or indexing untrusted fallback search results.
- Provide trusted-domain hints to the configured search provider when running fallback web search.
- Add regression coverage for untrusted fallback evidence being excluded from persistence.

**Non-Goals:**

- Do not change the approved-domain policy or validation semantics.
- Do not add a new persistence path, search provider, or dependency.
- Do not block assistant fallback answers solely because persistence finds no trusted results.
- Do not require frontend API changes.

## Decisions

1. Validate fallback evidence in `AssistantTools.ingest_web_evidence(...)` before document construction.

   Rationale: This is the last boundary before persistence and protects all current or future graph callers. It also keeps validation next to the knowledge document construction that needs trusted sources.

   Alternative considered: Filter only in the graph before calling ingestion. That would reduce current persisted inputs but leave `ingest_web_evidence(...)` unsafe for direct tests or future callers.

2. Pass `allowed_domains` from `TrustedSourceValidator.approved_domains` when `trusted_web_search(...)` calls the configured search provider.

   Rationale: The OpenAI search provider already accepts `allowed_domains`, and the acquisition service uses the same pattern. Passing the hint reduces untrusted results earlier while still requiring post-search validation before persistence.

   Alternative considered: Rely only on the provider prompt. Provider output cannot be treated as a security boundary, so local validation remains required.

3. Keep live web-answer filtering separate from persistence filtering.

   Rationale: The reported bug is persistent knowledge ingestion bypassing trust validation. If existing fallback answer generation uses usable search snippets for a degraded live answer, this change should not unexpectedly remove that user-facing fallback unless the implementation already requires trusted snippets.

   Alternative considered: Filter `web_results` in the graph before answer generation and persistence. That may be desirable later, but it changes assistant answer availability and is broader than the persistence defect.

4. Treat "no trusted fallback results" as a non-blocking ingestion failure.

   Rationale: Fallback persistence is best effort. Returning a `ToolResult` failure or limitation for no trusted results lets observability capture the skipped persistence without preventing the assistant response.

   Alternative considered: Silently return success with no document ID. That makes skipped persistence hard to detect in tests and logs.

## Risks / Trade-offs

- Trusted-domain configuration may be empty or too narrow -> Fallback persistence will be skipped with a clear failure/limitation instead of storing untrusted content.
- Search providers may ignore `allowed_domains` -> Local `TrustedSourceValidator` remains the authoritative persistence gate.
- Live fallback answers may still cite untrusted snippets if they pass existing usability checks -> This change intentionally targets persistence; answer-source trust requirements can be tightened in a separate capability change if needed.
