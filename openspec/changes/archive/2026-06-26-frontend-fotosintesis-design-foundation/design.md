## Context

`frontend/REFERENCES/fotosintesis/DESIGN.md` defines a Clean Botanical visual direction with warm paper surfaces, forest greens, soil browns, Bodoni Moda headlines, Roboto functional text, rounded shapes, tonal surfaces, low-contrast outlines, and botanical/material iconography. The current frontend has a minimal token file, global Arial fallback styling, limited shared UI primitives, and some product naming that still appears as `Fotosintesis AI` rather than the user-facing `Fotosíntesis` brand.

This change establishes the shared visual foundation so later feature-specific redesigns can use one consistent system. It is intentionally foundational: it may touch app metadata, global styles, tokens, and shared primitives, but it must not redesign garden, assistant, identification, reminders, auth, or light-meter screens beyond the smallest integration needed to prove the system works.

## Goals / Non-Goals

**Goals:**

- Encode the Fotosintesis reference palette, type scale, spacing, radius, surface, outline, and elevation decisions as shared SCSS tokens and global CSS custom properties.
- Load Bodoni Moda and Roboto through the app-level font mechanism and expose the pair through global styles and tokens.
- Standardize user-facing product naming as `Fotosíntesis`.
- Define how static mockups that contain placeholder copy such as `PlantCare` are adapted into the real product language before implementation.
- Provide shared UI primitives for buttons, cards, fields, chips, notices, page headers, and image cards.
- Define the icon strategy for botanical/material icons so later screens use consistent source, shape, color, sizing, and accessibility rules.
- Define responsive visual rules for later redesigns, including mobile and desktop margins, grid behavior, section spacing, and card density.
- Keep changes testable with focused component or style integration coverage where practical.

**Non-Goals:**

- No individual feature screen redesigns beyond a minimal proof-of-foundation use.
- No behavior changes to auth, garden, assistant, identification, reminders, light meter, API clients, data fetching, RAG, classifier, answerability, or backend flows.
- No new semantic plant-care heuristics, keyword matching, translated word lists, regex language detection, or hardcoded botanical classification logic.
- No wholesale replacement of existing feature component structure.
- No dark theme unless a future design reference explicitly defines one.

## Decisions

### Decision 1: Use SCSS variables plus CSS custom properties

The implementation should define canonical values in `frontend/src/styles/_tokens.scss` and emit app-wide CSS custom properties from `globals.scss` or a dedicated global token selector. SCSS variables serve module-level styles that already use Sass, while CSS custom properties allow primitives and future components to consume tokens without importing Sass into every file.

Alternative considered: CSS custom properties only. This was rejected because the current code already uses SCSS modules and Sass tokens, so removing Sass variables would create unnecessary churn.

### Decision 2: Preserve reference token names where possible

Colors should map closely to the reference names: `surface`, `surface-container-lowest`, `surface-container-low`, `surface-container`, `surface-container-high`, `surface-container-highest`, `on-surface`, `on-surface-variant`, `outline`, `outline-variant`, `primary`, `primary-container`, `on-primary`, `secondary`, `secondary-container`, `tertiary`, `error`, and related container/on-container colors. Semantic aliases may be added for common uses, but raw reference names remain available so future screen redesigns can trace decisions back to the reference.

Alternative considered: collapse the palette into a small `background/text/accent` set. This was rejected because the reference explicitly uses tonal surface layers and container variants for hierarchy.

### Decision 3: Normalize the brand as `Fotosíntesis` while keeping file/change IDs ASCII

User-facing UI text, metadata, and documentation for product display must use `Fotosíntesis` with the accent. File names, capability IDs, package names, and route identifiers remain ASCII/kebab-case where needed.

Mockups or generated references that say `PlantCare`, `Fotosintesis`, or `Fotosintesis AI` are source placeholders, not product copy. During implementation, `PlantCare` must be adapted to `Fotosíntesis` or to context-specific Spanish product copy. `Fotosintesis` may remain only in technical identifiers where accents are unsuitable.

Alternative considered: keep `Fotosintesis AI` because metadata already uses it. This was rejected because the requested product naming standard is `Fotosíntesis`.

### Decision 4: Load fonts through Next app fonts

Use the app's framework-level font loading mechanism for Google fonts, assigning Bodoni Moda to headings and Roboto to body/UI text. The fonts should expose CSS variables, for example `--font-headline` and `--font-body`, and global styles should use those variables with reliable fallbacks.

Alternative considered: `@import` in global CSS. This was rejected because framework-managed font loading avoids render-blocking stylesheet imports and gives better control over subsets, weights, and CSS variables.

### Decision 5: Build primitives as small shared components with class variants

Create or specify primitives under `frontend/src/components/ui/` for:

- `Button`: primary, secondary, outline/ghost, destructive when needed; supports link-like composition only if current app patterns require it.
- `Card`: tonal, elevated, outlined, and quiet surface variants.
- `Field`: label, help text, error text, input/textarea/select styling, and focus state using secondary brown.
- `Chip`: pill-shaped labels for categories/status.
- `Notice`: informational, success, warning, and error messages using container/on-container tokens.
- `PageHeader`: consistent eyebrow, title, description, actions, and optional botanical icon/art slot.
- `ImageCard`: rounded image container with caption, metadata chips, fallback surface, and responsive aspect ratios.

The primitives should be minimal and composable. Avoid introducing a large component abstraction layer or redesigning screens to consume every primitive immediately.

Alternative considered: introduce a third-party UI kit. This was rejected because the reference visual language is custom and the existing app is small enough to support lightweight primitives.

### Decision 6: Icons use a curated botanical/material strategy

Reference-style icons should be solid, simple, botanical or material-inspired, and rendered in token colors. Use primary green by default, secondary brown for callouts, and error color only for destructive/error states. Icons must be decorative with `aria-hidden` unless they convey unique information, in which case the component must provide an accessible label.

Implementation can use an existing icon package if already available, a small local SVG set, or add a narrowly scoped dependency only if that is the smallest maintainable option. Custom botanical icons should live in a shared location rather than being embedded ad hoc in feature screens.

Alternative considered: allow arbitrary icons per screen. This was rejected because it would fragment the visual system before screen redesigns begin.

### Decision 7: Responsive rules are tokenized constraints, not one-off media queries

Later screen redesigns must follow mobile 4-column rhythm with 16px margins and gutters, desktop 12-column rhythm with 32px margins and 24px gutters, and major vertical spacing of 40px or 64px. Shared layout helpers or documented CSS custom properties should expose page margins, gutters, content max widths, and section spacing.

Alternative considered: leave responsive behavior to each feature screen. This was rejected because the design foundation is meant to avoid per-screen visual drift.

## Risks / Trade-offs

- **Risk: Foundation work becomes a hidden screen redesign.** → Mitigation: limit feature screen edits to metadata/global integration and one minimal proof use of primitives.
- **Risk: Token names drift from the reference.** → Mitigation: preserve reference token names and add aliases only where they simplify component usage.
- **Risk: Font loading changes cause layout shifts or test instability.** → Mitigation: use framework-managed fonts with explicit weights/subsets and stable fallback font variables.
- **Risk: Primitive components become too broad too early.** → Mitigation: implement only the variants required by the reference and near-term screens; avoid speculative props.
- **Risk: Static mockup placeholder copy leaks into production.** → Mitigation: require explicit replacement of placeholder brand names and copy before adapting any reference mockup.
- **Risk: Icon dependency increases bundle size.** → Mitigation: prefer local/curated SVGs or tree-shakeable imports; document acceptable icon sources.

## Migration Plan

1. Replace the minimal SCSS token file with the Fotosintesis color, typography, spacing, radius, surface, outline, and elevation token set.
2. Update global styles to emit CSS custom properties, apply warm paper surfaces, set base text color, and use the loaded font variables.
3. Configure Bodoni Moda and Roboto in the root layout and update metadata brand text to `Fotosíntesis`.
4. Add the shared UI primitives and their SCSS modules under `frontend/src/components/ui/`.
5. Add or update a minimal proof integration, such as an existing placeholder/foundation component, without redesigning feature flows.
6. Add focused tests where useful to verify primitive rendering, accessible labels, and brand text.
7. Run frontend lint/type/test checks used by the project.

Rollback is source-only: revert the frontend style, component, and metadata changes. No data migration, backend change, API change, or persisted state migration is involved.

## Open Questions

No blocking open questions remain. If implementation needs an icon dependency, choose the smallest tree-shakeable option that can match the botanical/material style; otherwise use local SVG primitives.
