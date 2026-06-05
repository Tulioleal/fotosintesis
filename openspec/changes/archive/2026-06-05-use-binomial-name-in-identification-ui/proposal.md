## Why

Identification results currently rely on the full scientific name for display and navigation, which can be verbose when names include authority, variety or subspecies information. The UI and assistant handoff should prefer a concise binomial name for user-facing identification context and plant-care searches while preserving the full scientific name as taxonomic context.

## What Changes

- Prefer `common_name`, then `binomial_name`, then existing scientific-name fallbacks when rendering identification candidate primary text.
- Show the full scientific name as secondary context only when it differs from the primary display name.
- Add binomial-aware assistant navigation from identification results using separate `plant`, `binomial` and `scientific` query parameters.
- Extend the frontend assistant request payload to send `plant_binomial_name` and `plant_scientific_name` when available while preserving compatibility with the existing `plant` field.
- Add frontend test coverage for binomial display, assistant handoff and existing fallback behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `plant-identification-taxonomy`: Identification candidate presentation and navigation should use binomial names when available while preserving full scientific names as secondary context.
- `assistant-agent`: Assistant chat requests should accept separated binomial and scientific plant context from the frontend and remain compatible with existing `plant`-only requests.

## Impact

- Affected frontend components: `frontend/src/components/identify/IdentifyFlow.tsx`, `frontend/src/components/assistant/AssistantChat.tsx`.
- Affected frontend API client: `frontend/src/lib/api/client.ts`.
- Affected tests: `frontend/src/components/identify/IdentifyFlow.test.tsx`, `frontend/src/components/assistant/AssistantChat.test.tsx`.
- Affected API contract: assistant chat request shape gains optional plant context fields; existing `plant` remains supported.
- No database migration or data backfill is included in this UI-focused change.
