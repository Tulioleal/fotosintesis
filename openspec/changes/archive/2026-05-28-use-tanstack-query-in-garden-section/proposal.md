## Why

The garden section currently fetches browser data with component-local `useEffect`, `useState`, and direct `fetch` calls, which diverges from the repo convention already used by Home with TanStack Query and the shared API client boundary. Aligning garden data access now will make loading, error, retry, cache invalidation, and test behavior consistent across protected frontend sections.

## What Changes

- Refactor garden list and detail data loading to use TanStack Query instead of ad hoc effect-driven fetch state.
- Move garden API calls behind the existing frontend API client pattern using generated OpenAPI types where available.
- Convert garden save/delete flows to mutation-style operations that invalidate or update related garden queries after success.
- Preserve the existing Next.js API route boundary for protected garden requests.
- Add or update frontend component tests for garden loading, error, empty, success, search, save, and delete mutation states.

## Capabilities

### New Capabilities

- `garden-query-data-fetching`: Defines TanStack Query-based data fetching and mutation behavior for the garden list, garden detail, and save/delete garden interactions.

### Modified Capabilities

- `openapi-typescript-client`: Garden frontend API wrappers must use generated OpenAPI request and response types for consumed garden endpoints where those contracts exist.
- `frontend-component-test-coverage`: Frontend component coverage must include garden query and mutation states introduced by this change.

## Impact

- Affected frontend components: `GardenList`, `GardenDetail`, and `PlantProfileView`.
- Affected frontend API code: `frontend/src/lib/api/client.ts` or adjacent garden-specific API wrapper modules.
- Affected tests: garden component tests and any shared query provider test utilities needed for TanStack Query.
- No backend API or database changes are expected.
