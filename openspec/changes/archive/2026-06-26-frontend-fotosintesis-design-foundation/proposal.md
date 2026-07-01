## Why

The frontend has working feature flows, but its screens and components do not yet share the cohesive Fotosintesis visual system defined in `frontend/REFERENCES/fotosintesis/DESIGN.md`. Establishing the shared foundation first prevents each later screen redesign from inventing colors, typography, spacing, components, and brand language independently.

## What Changes

- Translate the Fotosintesis reference colors, typography, spacing, radii, surface layers, outlines, and elevation guidance into shared frontend design tokens.
- Standardize user-facing product naming as `Fotosíntesis`, including metadata and brand text touched by the foundation work.
- Define how static reference mockups must be adapted when they contain placeholder copy such as `PlantCare`, so placeholders never ship as product language.
- Define Bodoni Moda and Roboto font loading for the app shell and global styles.
- Define the icon strategy for reference-style botanical/material icons, including color usage and when custom icons are required.
- Introduce or specify shared UI primitives for buttons, cards, fields, chips, notices, page headers, and image cards.
- Define responsive visual rules for desktop and mobile layouts that later screen redesigns must follow.
- Add only minimal usage needed to prove the foundation works; this change does not redesign individual feature screens.

## Capabilities

### New Capabilities

- `frontend-visual-system`: Defines the shared Fotosintesis frontend visual foundation, including design tokens, brand naming, reference adaptation rules, font and icon strategy, UI primitives, and responsive visual constraints.

### Modified Capabilities

No existing capability requirements are modified.

## Impact

- Affected frontend areas:
  - `frontend/src/styles/_tokens.scss`
  - `frontend/src/styles/globals.scss`
  - shared UI components under `frontend/src/components/ui/`
  - app layout metadata and brand text where needed
  - visual-system documentation/specs for future frontend redesign work
- No backend API, database, authentication, plant-care behavior, RAG behavior, or assistant behavior changes are intended.
- No individual feature screen redesign is included beyond minimal integration needed to verify tokens, fonts, and primitives render correctly.
