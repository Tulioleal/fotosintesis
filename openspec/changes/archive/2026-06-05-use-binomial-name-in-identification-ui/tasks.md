## 1. Identification UI

- [x] 1.1 Update `frontend/src/components/identify/IdentifyFlow.tsx` candidate typing to include nullable `binomial_name`.
- [x] 1.2 Add candidate display/search/scientific fallback values using `common_name`, `binomial_name`, `accepted_scientific_name` and `suggested_scientific_name` in the documented priority order.
- [x] 1.3 Render the primary candidate label from the display fallback and render the full scientific name only as secondary text when it differs from the primary label.
- [x] 1.4 Update identification-to-assistant navigation to include encoded `plant`, `binomial` and `scientific` query parameters when values are available.

## 2. Assistant Context Payload

- [x] 2.1 Update `frontend/src/components/assistant/AssistantChat.tsx` to read `binomial` and `scientific` query parameters in addition to the existing `plant` parameter.
- [x] 2.2 Update `frontend/src/lib/api/client.ts` assistant request typing and payload creation to send optional `plant_binomial_name` and `plant_scientific_name` while preserving the existing `plant` field.
- [x] 2.3 Update the backend assistant chat request schema and service/graph handoff to accept `plant_binomial_name` and `plant_scientific_name` and prefer binomial context for plant lookup/search operations.
- [x] 2.4 Preserve compatibility for existing assistant requests and URLs that only provide `plant`.

## 3. Tests And Verification

- [x] 3.1 Update `frontend/src/components/identify/IdentifyFlow.test.tsx` to verify binomial primary rendering when `common_name` is absent.
- [x] 3.2 Update identification UI tests to verify fallback to accepted or suggested scientific name when `binomial_name` is absent.
- [x] 3.3 Update identification UI tests to verify assistant links include separated `plant`, `binomial` and `scientific` query parameters.
- [x] 3.4 Update `frontend/src/components/assistant/AssistantChat.test.tsx` to verify chat requests include `plant_binomial_name` and `plant_scientific_name` when query parameters are present.
- [x] 3.5 Add or update backend assistant tests proving binomial context is preferred and plant-only requests still work.
- [x] 3.6 Run the relevant frontend and backend test suites for the changed components and assistant request handling.
