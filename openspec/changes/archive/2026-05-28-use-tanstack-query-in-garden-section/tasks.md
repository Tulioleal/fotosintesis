## 1. API Client Layer

- [x] 1.1 Add typed garden list, detail, save, and delete functions to the frontend API client layer using generated OpenAPI request and response types.
- [x] 1.2 Ensure browser garden client functions call `/api/garden` and `/api/garden/{gardenId}` instead of protected backend URLs directly.
- [x] 1.3 Preserve garden route error details by converting failed API responses into user-facing errors that components can render.

## 2. Garden Query Reads

- [x] 2.1 Refactor `GardenList` to use `useQuery` with a garden list query key that includes submitted search text.
- [x] 2.2 Preserve submit-driven search behavior and existing loading, empty, error, and success rendering in `GardenList`.
- [x] 2.3 Refactor `GardenDetail` to use `useQuery` with a garden detail query key scoped by `gardenId`.
- [x] 2.4 Preserve existing garden detail loading and error states while removing component-local effect-driven fetch state.

## 3. Garden Mutations

- [x] 3.1 Refactor `PlantProfileView` garden save behavior to use `useMutation` and the typed garden save client function.
- [x] 3.2 Invalidate garden list queries after a successful garden save and preserve the saved confirmation message.
- [x] 3.3 Refactor `GardenDetail` delete behavior to use `useMutation` and the typed garden delete client function.
- [x] 3.4 Preserve reminder-confirmation conflict handling and retry deletion with confirmation.
- [x] 3.5 Invalidate affected garden list/detail queries after successful deletion before navigating back to Mi Jardin.

## 4. Component Tests

- [x] 4.1 Add or update garden test utilities so components render with an isolated TanStack Query client.
- [x] 4.2 Add `GardenList` tests for loading, empty, error, success, and submitted search behavior.
- [x] 4.3 Add `GardenDetail` tests for loading/error states, delete conflict confirmation, and successful delete navigation.
- [x] 4.4 Add `PlantProfileView` tests for garden save success and failure mutation states.

## 5. Verification

- [x] 5.1 Run frontend type checking and fix any TypeScript errors introduced by generated garden types.
- [x] 5.2 Run frontend component tests covering the garden query and mutation flows.
- [x] 5.3 Run OpenSpec validation/status checks for `use-tanstack-query-in-garden-section`.
