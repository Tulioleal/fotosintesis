## ADDED Requirements

### Requirement: Shared private route layout
The frontend SHALL render authenticated product routes through a shared Next.js `(private)` route layout that applies the private Fotosíntesis shell once per route.

#### Scenario: Private routes render inside the shared shell
- **WHEN** an authenticated user opens `/home`, `/identify`, `/search`, `/light-meter`, `/reminders`, `/garden`, a garden detail route, a plant profile route, or `/assistant`
- **THEN** the route content renders inside the shared private shell
- **AND** the page module or shared page component does not wrap itself manually with `AppShell`

#### Scenario: Private route protection remains unchanged
- **WHEN** an unauthenticated navigation targets a protected private route
- **THEN** the existing server-side private route protection redirects to `/login` with the current callback behavior
- **AND** the shell implementation does not introduce a competing client-side session gate

#### Scenario: Deeper feature pages keep their behavior
- **WHEN** existing feature pages render inside the shared shell
- **THEN** their existing data fetching, forms, placeholders, and feature-specific content continue to work without a visual redesign beyond shell canvas integration

### Requirement: Desktop private top bar
The shared private shell SHALL provide a Fotosíntesis desktop top bar for authenticated routes.

#### Scenario: Desktop top bar renders
- **WHEN** an authenticated private route is viewed at desktop width
- **THEN** the shell shows a top bar with the `Fotosíntesis` brand, private navigation, and account/logout affordance
- **AND** the top bar uses the archived Fotosíntesis visual foundation for typography, color, spacing, outlines, and interactive states

#### Scenario: Desktop navigation remains accessible
- **WHEN** assistive technology inspects the desktop private navigation
- **THEN** navigation landmarks and links expose stable accessible names for the private sections
- **AND** active route state is available visually and semantically without relying only on color

### Requirement: Mobile private bottom navigation
The shared private shell SHALL provide a mobile bottom navigation for the main authenticated sections.

#### Scenario: Mobile bottom navigation renders
- **WHEN** an authenticated private route is viewed at mobile width
- **THEN** the shell shows bottom navigation with the existing private section names used by the app tests
- **AND** the active section is visually indicated
- **AND** the navigation remains reachable by accessible name

#### Scenario: Mobile navigation does not obscure content
- **WHEN** private content extends below the fold on a mobile viewport
- **THEN** the shell provides enough bottom spacing and safe-area handling for content and actions to remain reachable above the fixed navigation

### Requirement: Private page canvas and footer
The shared private shell SHALL provide consistent page canvas spacing and footer behavior for authenticated routes.

#### Scenario: Page canvas follows the Fotosíntesis grid
- **WHEN** private route content renders
- **THEN** the main canvas uses the Fotosíntesis responsive margin, gutter, max-width, surface, and section-spacing rules

#### Scenario: Footer behavior follows the shell context
- **WHEN** a private route has enough viewport height or content length to show the app footer
- **THEN** the footer uses `Fotosíntesis` product naming, visual-system surfaces, and responsive layout
- **AND** it does not conflict with the mobile bottom navigation
