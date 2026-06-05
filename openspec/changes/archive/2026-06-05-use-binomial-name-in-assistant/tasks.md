## 1. Backend Request Contract

- [x] 1.1 Add optional nullable `plant_binomial_name` and `plant_scientific_name` fields to the assistant chat request schema in `backend/app/assistant/schemas.py` while preserving `plant`.
- [x] 1.2 Add or update backend request parsing tests to confirm existing `plant`-only payloads still validate.

## 2. Backend Name Selection

- [x] 2.1 Implement shared assistant name selection for operational plant name priority: `plant_binomial_name`, then `plant_scientific_name`, then `plant`.
- [x] 2.2 Implement shared display/context plant name priority: `plant`, then `plant_scientific_name`, then `plant_binomial_name`.
- [x] 2.3 Normalize blank plant-name inputs so empty strings do not override later non-empty fallback values.

## 3. Assistant Graph And Tools

- [x] 3.1 Pass the derived operational and display/context plant names from `backend/app/assistant/service.py` into assistant graph state or equivalent request context.
- [x] 3.2 Update `backend/app/assistant/graph.py` so RAG retrieval, plant-data lookup, trusted web fallback, and answer prompt context use the correct derived name for each purpose.
- [x] 3.3 Update `backend/app/assistant/tools.py` or related tool call construction so web search, structured plant-data APIs, RAG acquisition, and trusted web fallback receive the operational plant name.
- [x] 3.4 Preserve `plant_scientific_name` as taxonomic context where prompt or metadata context is assembled.

## 4. Backend Tests

- [x] 4.1 Add a backend test proving `plant_binomial_name` is used for search/tool/RAG operations when provided.
- [x] 4.2 Add a backend test proving `plant_scientific_name` is used when `plant_binomial_name` is missing.
- [x] 4.3 Add a backend test proving `plant` is used when both new fields are missing.
- [x] 4.4 Add a backend test proving user-facing/display context prefers `plant` when it differs from the binomial name.
- [x] 4.5 Run targeted backend tests, for example `pytest tests/test_assistant_agent.py` from `backend/`.

## 5. Frontend Contract And Chat Payload

- [x] 5.1 Regenerate frontend OpenAPI artifacts with `pnpm --filter frontend openapi:generate` after the backend schema change.
- [x] 5.2 Update `frontend/src/lib/api/client.ts` so assistant chat request payloads accept and forward `plant_binomial_name` and `plant_scientific_name`.
- [x] 5.3 Update `frontend/src/components/assistant/AssistantChat.tsx` to read `plant`, `binomial`, and `scientific` query parameters and send the corresponding backend payload fields.
- [x] 5.4 Update assistant initial context rendering to show the display plant and concise binomial context without showing verbose full scientific names by default.

## 6. Frontend Assistant Entry Links

- [x] 6.1 Update `frontend/src/components/identify/IdentifyFlow.tsx` assistant links to send `plant`, `binomial`, and `scientific` query parameters using the requested identification priority.
- [x] 6.2 Update `frontend/src/components/garden/PlantProfileView.tsx` assistant links to include `binomial` and `scientific` when both fields are exposed by the profile data.
- [x] 6.3 Update `frontend/src/components/garden/GardenDetail.tsx` assistant links to include `binomial` and `scientific` when both fields are exposed by garden/profile data.
- [x] 6.4 Keep garden/profile links working when `binomial_name` is not exposed yet by falling back to existing `plant` and available `scientific` context.

## 7. Frontend Tests And Verification

- [x] 7.1 Update assistant component tests to verify query parameter mapping and payload fields.
- [x] 7.2 Update identification and garden/profile link tests to verify assistant URLs include taxonomy query parameters when data is available.
- [x] 7.3 Run targeted frontend tests, for example `pnpm --filter frontend test -- AssistantChat IdentifyFlow PlantProfileView GardenDetail`.
- [x] 7.4 Run frontend type checking with `pnpm --filter frontend typecheck`.
