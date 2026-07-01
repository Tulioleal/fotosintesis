## 1. Route Shell Structure

- [x] 1.1 Add `frontend/src/app/(private)/layout.tsx` that wraps private route children in `AppShell` without adding new auth/session logic.
- [x] 1.2 Move `/home` into `frontend/src/app/(private)/home/page.tsx` and remove the old `frontend/src/app/home/page.tsx` so the URL stays `/home` without duplicate route definitions.
- [x] 1.3 Remove manual `AppShell` wrapping from private page modules and shared page components such as `PlaceholderPage`.
- [x] 1.4 Verify private route protection still comes from existing middleware and unauthenticated `/home` navigation still redirects to `/login` with callback behavior.

## 2. Private Shell Redesign

- [x] 2.1 Refactor `AppShell` to own the desktop top bar, main page canvas, mobile bottom navigation, and footer behavior for private routes.
- [x] 2.2 Redesign `AppShell.module.scss` with Fotosíntesis tokens for botanical surfaces, desktop and mobile spacing, sticky top bar, safe-area-aware mobile bottom padding, active states, and footer layout.
- [x] 2.3 Update `BottomNavigation` to keep stable accessible navigation names, active section semantics, and mobile-only presentation inside the shared shell.
- [x] 2.4 Ensure logout/account affordances remain available and do not expose browser-visible backend credentials.

## 3. Home Dashboard Redesign

- [x] 3.1 Refactor `HomeDashboard` markup to follow the dashboard mosaic reference: welcome section, primary identification card, quick-access mosaic, secondary/featured content rhythm, empty state, and retry/error states.
- [x] 3.2 Preserve the existing `useSession` gate, TanStack Query key, `apiClient.getHomeSummary()` call, retry count, loading skeleton, error message, retry button, and empty-state behavior.
- [x] 3.3 Adapt reference placeholder copy from `PlantCare` to `Fotosíntesis` and keep backend `GET /home/summary` labels/data flow unchanged.
- [x] 3.4 Redesign `HomeDashboard.module.scss` with Fotosíntesis tokens, responsive grid behavior, rounded image/card treatments, outline surfaces, and mobile spacing that clears the bottom navigation.

## 4. Tests and Verification

- [x] 4.1 Update Home component tests for the redesigned DOM while preserving loading, empty, error, retry, and API-call assertions.
- [x] 4.2 Add or update route/shell tests proving private pages are shell-wrapped through the shared `(private)` layout rather than manual wrappers where practical.
- [x] 4.3 Update e2e/auth navigation assertions only where the spec intentionally changes visible copy; otherwise preserve current accessible names used by tests.
- [x] 4.4 Run relevant frontend tests for Home, auth/session boundary, navigation, and private route redirect behavior.
- [x] 4.5 Run OpenSpec validation/status for `frontend-private-shell-home-redesign` and resolve any artifact or spec formatting issues.
