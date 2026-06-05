## Why

Assistant requests currently carry a single `plant` value that is suitable for display but can be a common name, cultivar-like label, or full infraspecific scientific name. Search, structured plant-data APIs, and RAG acquisition need a stable binomial name when available, while the assistant should still preserve the full scientific name as taxonomic context and keep existing `plant` payloads working.

## What Changes

- Extend the assistant chat request contract with optional `plant_binomial_name` and `plant_scientific_name` fields while retaining `plant` for display and compatibility.
- Use plant names with explicit priority in assistant backend flows: operational search/API/RAG name uses `plant_binomial_name`, then `plant_scientific_name`, then `plant`; display/context name uses `plant`, then `plant_scientific_name`, then `plant_binomial_name`.
- Update assistant tools and fallback paths that perform web search, structured plant-data lookup, RAG retrieval/acquisition, or trusted web fallback to use the operational plant name.
- Add backend tests for binomial priority, scientific-name fallback, legacy `plant` fallback, and compatibility with existing `plant`-only payloads.
- Regenerate frontend OpenAPI types and update the frontend chat client to send the new optional fields.
- Update assistant entry links from identification and garden/profile views to pass display, binomial, and scientific context when available.
- Update the assistant UI to show the display plant and concise binomial context without surfacing overly verbose full scientific names by default.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Assistant chat request and orchestration behavior changes to distinguish display plant context from operational plant search/API/RAG context.
- `knowledge-rag-acquisition`: Runtime retrieval/acquisition and trusted fallback evidence persistence use the prioritized operational plant name.
- `structured-plant-data-lookup`: Structured plant-data lookup uses the prioritized operational scientific/binomial name when available.
- `openapi-typescript-client`: Generated frontend contracts and frontend chat wrappers include the new optional assistant request fields.

## Impact

- Backend API schema: `backend/app/assistant/schemas.py` assistant chat request gains two optional nullable fields.
- Backend assistant orchestration: likely `backend/app/assistant/service.py`, `backend/app/assistant/graph.py`, and assistant tool call construction need explicit operational/display name handling.
- Backend tests: assistant service/graph/tool tests need coverage for name priority and legacy payload compatibility.
- Frontend API contracts: OpenAPI TypeScript artifacts must be regenerated with `pnpm --filter frontend openapi:generate`.
- Frontend chat/client/UI: `frontend/src/lib/api/client.ts`, `frontend/src/components/assistant/AssistantChat.tsx`, and assistant links in identification and garden/profile views need updated query parameters and payload mapping.
