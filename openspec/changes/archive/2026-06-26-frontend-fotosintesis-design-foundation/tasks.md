## 1. Baseline and References

- [x] 1.1 Inspect current frontend styles, metadata, shared UI components, and package font/icon dependencies.
- [x] 1.2 Compare current style tokens against `frontend/REFERENCES/fotosintesis/DESIGN.md` and record any token names that need aliases for existing SCSS modules.
- [x] 1.3 Search frontend user-facing copy for `Fotosintesis`, `Fotosintesis AI`, `PlantCare`, and other placeholder product names.

## 2. Tokens and Global Styles

- [x] 2.1 Replace `frontend/src/styles/_tokens.scss` with the Fotosintesis color, typography, spacing, radius, surface, outline, and elevation tokens.
- [x] 2.2 Emit app-wide CSS custom properties for the shared visual-system tokens in global styles.
- [x] 2.3 Update global body, heading, control, focus, link, selection, and media defaults to use the tokenized warm surface, text colors, and font variables.
- [x] 2.4 Preserve or add compatibility aliases only where existing SCSS modules still need them during the foundation-only rollout.

## 3. Fonts and Brand Metadata

- [x] 3.1 Configure Bodoni Moda and Roboto through the app-level font loading mechanism with required weights and CSS variables.
- [x] 3.2 Apply the font variables in `frontend/src/app/layout.tsx` and global styles.
- [x] 3.3 Update app metadata and touched user-facing brand copy to use `Fotosíntesis`.
- [x] 3.4 Replace any discovered `PlantCare` placeholder copy in frontend implementation paths with `Fotosíntesis` or accurate Spanish context copy.

## 4. Shared UI Primitives

- [x] 4.1 Add or update a shared button primitive with primary, secondary, outline or ghost, and destructive/error variants.
- [x] 4.2 Add or update a shared card primitive with tonal, outlined, quiet, and elevated surface variants.
- [x] 4.3 Add or update a shared field primitive for labels, controls, help text, error text, focus states, and accessible descriptions.
- [x] 4.4 Add or update shared chip and notice primitives using tokenized container and text colors.
- [x] 4.5 Add or update shared page header and image card primitives with responsive spacing, rounded surfaces, image fallback, and optional action/art slots.
- [x] 4.6 Export primitives from a consistent `frontend/src/components/ui/` entry point if the project has or needs one.

## 5. Icon Strategy

- [x] 5.1 Decide whether the existing dependency set supports the botanical/material icon strategy or whether a small local SVG set is sufficient.
- [x] 5.2 Add shared icon utilities or components for reference-style icons with token color variants and size rules.
- [x] 5.3 Ensure decorative icons are hidden from assistive technology and informative icons accept accessible labels.

## 6. Responsive Foundation and Proof Integration

- [x] 6.1 Add shared responsive layout variables or helpers for mobile margins/gutters, desktop margins/gutters, content width, and major section spacing.
- [x] 6.2 Integrate the new primitives in one minimal existing UI path, such as the placeholder page, to prove the foundation works without redesigning feature screens.
- [x] 6.3 Verify no feature page received a screen-level redesign as part of this foundation change.

## 7. Tests and Verification

- [x] 7.1 Add focused component tests for any new primitives that have behavior, accessibility labels, or variant-specific rendering.
- [x] 7.2 Add or update a test that verifies the user-facing app brand renders as `Fotosíntesis` where metadata or visible brand text is covered by tests.
- [x] 7.3 Run the frontend lint/type/test command set used by the project.
- [x] 7.4 Manually inspect the minimal proof integration on mobile and desktop widths.
- [x] 7.5 Confirm no backend, API, assistant, retrieval, classifier, evidence, or plant-care semantic behavior changed.
