## Context

The archived Fotosíntesis visual foundation defines the product palette, typography, spacing, radius, icon, and reference-adaptation rules. The current authenticated frontend applies shell chrome inconsistently: some private pages wrap themselves with `AppShell`, some receive the shell indirectly through shared placeholder components, and `/home` sits outside the `(private)` route group while still being protected by middleware.

The redesign must preserve the existing authentication boundary, server-side private route redirects, Auth.js session handling, the frontend `/api/home/summary` bridge, TanStack Query loading/error behavior, generated API types, and backend `GET /home/summary` semantics. The backend home access labels remain the English API contract; visible shell and Home copy may adapt reference placeholders into the Fotosíntesis product voice without changing the API response.

## Goals / Non-Goals

**Goals:**

- Centralize authenticated route chrome in `frontend/src/app/(private)/layout.tsx` so protected pages do not manually wrap themselves with `AppShell`.
- Move `/home` into the `(private)` route group while keeping the public URL `/home` unchanged.
- Redesign `AppShell`, `BottomNavigation`, and shell styles around the archived Fotosíntesis design system: botanical surfaces, Bodoni Moda headings, Roboto functional text, desktop top bar, mobile bottom navigation, responsive canvas spacing, and footer behavior.
- Redesign `HomeDashboard` using the dashboard mosaic reference as visual direction while preserving `GET /home/summary`, TanStack Query, loading, error, empty, and retry behavior.
- Preserve existing private-route protection, redirects, session validation, and deeper feature page behavior.

**Non-Goals:**

- Redesigning identification, search, garden, reminders, light meter, assistant, garden detail, or plant profile feature bodies beyond fitting them inside the shared shell canvas.
- Changing backend endpoints, Auth.js/session storage, middleware protection semantics, generated OpenAPI contracts, or the English `GET /home/summary` access label contract.
- Introducing new visual libraries, new authentication providers, or new botanical semantics.

## Decisions

1. Use the Next.js route group layout as the shell boundary.

   `frontend/src/app/(private)/layout.tsx` will render `AppShell` around `children`. `/home` should move to `frontend/src/app/(private)/home/page.tsx` so it shares the same layout without changing the `/home` URL. This is preferable to continuing manual page wrappers because the shell becomes a single structural concern and private pages cannot drift visually by omission.

   Alternative considered: keep `/home` outside `(private)` and keep manual `AppShell` wrappers. That preserves fewer file moves, but it leaves the exact duplication this change is intended to remove.

2. Keep auth protection outside the visual shell.

   Middleware and existing server/session helpers remain responsible for redirecting unauthenticated users. The private layout will provide chrome only; it will not duplicate session validation. This avoids conflicting auth sources and preserves current redirect behavior and tests.

   Alternative considered: validate session inside the layout. That couples visual layout to auth enforcement and risks changing redirect timing or callback behavior.

3. Make `AppShell` a structural component, not a page-specific wrapper.

   `AppShell` should own the desktop top bar, mobile bottom navigation, main content canvas, and footer behavior. Private pages and shared feature components should render their content directly, with `PlaceholderPage` no longer wrapping itself in `AppShell`.

   Alternative considered: split shell into multiple exported wrappers. That adds names and integration points without a concrete reuse need.

4. Preserve backend API labels while adapting visible reference copy.

   The Home dashboard should keep using the API access data and generated types, but the reference's `PlantCare` copy must become `Fotosíntesis`. Existing hardcoded Home CTAs and shell navigation accessible names should remain stable unless the spec explicitly changes them. This balances the project-foundation requirement for English backend labels with the product requirement for Spanish Fotosíntesis-facing copy.

   Alternative considered: translate API labels in the frontend for all Home cards. That would conflict with the current project-foundation spec requiring direct use of backend labels.

5. Use the reference as visual direction, not literal markup.

   The implementation should translate the dashboard mosaic reference into SCSS modules and existing React components rather than importing reference HTML, Tailwind CDN classes, remote placeholder imagery, or generated scripts. This keeps the app aligned with the established CSS module/token architecture.

   Alternative considered: port the reference HTML directly. That would introduce CDN/Tailwind assumptions and placeholder assets that do not match the current app architecture.

## Risks / Trade-offs

- Route move may create duplicate `/home` route files if the old file is not removed -> Remove the old `frontend/src/app/home/page.tsx` when adding `frontend/src/app/(private)/home/page.tsx` and verify route tests.
- Layout wrapping can accidentally double-wrap pages that still use `AppShell` -> Remove manual `AppShell` imports/usages from private pages and shared placeholder components during implementation.
- Mobile bottom navigation can obscure page content -> Add shell bottom padding/safe-area handling on mobile and keep footer behavior responsive.
- Visual redesign can break accessibility queries -> Preserve accessible navigation labels covered by tests and update tests only for intentional spec-backed copy changes.
- Home redesign can accidentally alter API flow -> Keep the existing `useSession` gate, TanStack Query key, `apiClient.getHomeSummary()`, retry, loading, error, and retry action behavior.

## Migration Plan

1. Add the private layout and move `/home` into the route group while deleting the old route file.
2. Refactor private pages and `PlaceholderPage` to remove manual `AppShell` wrapping.
3. Redesign shell components/styles, then verify each private route still renders inside the shell.
4. Redesign Home dashboard styles/markup against the mosaic reference while preserving data flow and states.
5. Update focused frontend tests for shell ownership, Home states, and navigation accessibility; run relevant frontend tests and e2e coverage where feasible.

Rollback is limited to reverting the route move and restoring manual wrappers, because no backend data or persisted client state migration is introduced.

## Open Questions

- None. The implementation can proceed with the archived Fotosíntesis design foundation and the provided dashboard mosaic reference.
