## Context

The protected garden section currently performs browser-side requests directly inside components with local loading, error, and data state. Home already uses TanStack Query with the frontend-owned API client and a Next.js route boundary for protected data. Garden endpoints are already available through frontend API routes and generated OpenAPI contracts, so this change is primarily a frontend data-access alignment rather than a backend API change.

The garden section has three relevant flows:

- Listing saved plants, optionally filtered by search text.
- Loading a saved plant detail by garden id.
- Saving or deleting garden plants from profile and detail screens.

## Goals / Non-Goals

**Goals:**

- Use TanStack Query for garden list and detail reads.
- Use TanStack Query mutations for garden save and delete writes.
- Centralize garden request functions in the frontend API client layer, typed from generated OpenAPI contracts where available.
- Keep protected browser calls routed through the existing Next.js API route boundary.
- Add tests around the user-visible query and mutation states.

**Non-Goals:**

- Change backend garden endpoint behavior or persistence.
- Introduce a new data fetching library or replace the existing QueryClient provider.
- Redesign the garden UI beyond state handling required by query and mutation behavior.
- Add optimistic updates unless they are necessary for existing UX parity.

## Decisions

1. Use query keys scoped by garden resource and input.

   Garden list reads will use keys such as `["garden", "list", search]`, and detail reads will use `["garden", "detail", gardenId]`. This keeps search results independently cached and makes invalidation after writes targeted without inventing a new cache abstraction.

   Alternative considered: use a single `["garden"]` key for all reads. That is simpler, but it makes detail/list cache invalidation less precise and can cause unrelated garden views to refetch unnecessarily.

2. Put garden request functions behind the API client layer.

   Components should call typed request functions such as list, get, save, and delete rather than constructing `fetch` calls inline. This follows the Home convention and gives one place to preserve route-boundary behavior, parse response errors, and apply generated OpenAPI types.

   Alternative considered: keep inline `fetch` inside query functions. That would still use TanStack Query, but it would not fix the repo-convention issue that garden request details are currently duplicated in components.

3. Use mutations plus invalidation for save and delete.

   Save success should invalidate garden list queries so newly saved plants appear in Mi Jardin. Delete success should invalidate garden list queries and remove or invalidate the deleted detail query before navigating back to the garden list.

   Alternative considered: perform only router navigation after writes. That preserves current behavior, but it leaves stale cached garden data once TanStack Query owns reads.

4. Preserve existing protected API route boundaries.

   Browser-executed garden calls should continue to call `/api/garden` and `/api/garden/{id}` rather than the backend base URL directly. This keeps backend credentials and protected session handling server-owned.

   Alternative considered: call backend routes directly from the browser API client. That conflicts with the existing secure session boundary and is out of scope.

## Risks / Trade-offs

- Query cache state can leak between tests if a shared QueryClient is reused -> create fresh test clients or reuse the existing provider test pattern with isolated clients.
- Search input can refetch too aggressively if wired to every keystroke -> preserve submit-driven search unless implementation intentionally adds debounce with tests.
- Error messages may become less specific if the API client throws generic errors -> parse route response payload details before throwing where garden UI depends on user-facing messages.
- Mutation invalidation can cause extra requests -> scope invalidation to garden list/detail keys rather than invalidating all queries.

## Migration Plan

1. Add typed garden API client functions while keeping existing API routes unchanged.
2. Refactor garden reads to `useQuery` and preserve existing loading, empty, error, and retry affordances.
3. Refactor save/delete to `useMutation` and invalidate related garden queries on success.
4. Add component tests for query and mutation states.
5. Run frontend lint/type/test verification.

Rollback is straightforward because the change is frontend-only: revert the component and client changes while leaving backend routes and generated contracts untouched.

## Open Questions

- None currently. The existing UI appears to use submit-driven search, so implementation should preserve that behavior unless a later requirement changes it.
