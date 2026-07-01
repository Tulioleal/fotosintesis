## Why

The Fotosíntesis visual foundation is complete, but the authenticated app still applies private chrome page-by-page and `/home` does not yet reflect the finalized dashboard direction. Centralizing the private shell now gives every protected route a consistent navigation frame before deeper feature screens are redesigned.

## What Changes

- Add a shared Next.js `(private)` route layout that owns the authenticated app chrome for private routes.
- Move private route shell concerns out of individual pages so private screens render inside one consistent Fotosíntesis frame.
- Redesign the private app shell around the archived Fotosíntesis visual system, including desktop top bar, mobile bottom navigation, page canvas spacing, and footer behavior where applicable.
- Redesign `/home` to visually follow `frontend/REFERENCES/dashboard_mosaic_edition/screen.png` and `frontend/REFERENCES/dashboard_mosaic_edition/code.html` while adapting placeholder `PlantCare` copy to `Fotosíntesis`.
- Preserve private-route protection, redirects, session handling, TanStack Query home fetching, generated API/client data flow, and accessible navigation names currently used by tests unless explicitly updated by spec.
- Avoid redesigning deeper feature pages beyond ensuring they render correctly inside the new private shell.

## Capabilities

### New Capabilities

- `private-app-shell`: Covers the shared authenticated route shell, desktop and mobile navigation chrome, page canvas behavior, and footer behavior for protected frontend routes.

### Modified Capabilities

- `authentication-home`: Updates Home presentation requirements so `/home` follows the dashboard mosaic reference while preserving authenticated data loading, route protection, and existing access labels.
- `frontend-visual-system`: Extends application of the archived Fotosíntesis visual foundation from design tokens/primitives into the authenticated shell and Home dashboard.

## Impact

- Affected frontend routes include `frontend/src/app/(private)/layout.tsx`, existing private route pages currently wrapping with `AppShell`, and `/home` placement/wrapping as needed for the shared private layout.
- Affected shell and dashboard components include `AppShell`, `BottomNavigation`, `AppShell.module.scss`, `HomeDashboard`, and `HomeDashboard.module.scss`.
- Relevant tests include Home component tests, auth/private navigation tests, and any route-shell/navigation assertions that depend on accessible names.
- No backend API contract, auth provider, session storage, redirect semantics, or deeper feature behavior is intended to change.
