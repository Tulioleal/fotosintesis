## ADDED Requirements

### Requirement: Fotosintesis design tokens
The frontend SHALL expose the Fotosintesis visual foundation as shared tokens for colors, typography, spacing, radii, surfaces, outlines, and elevation.

#### Scenario: Reference colors are available as tokens
- **WHEN** frontend styles are authored
- **THEN** the Fotosintesis reference palette from `frontend/REFERENCES/fotosintesis/DESIGN.md` is available through shared SCSS tokens and app-wide CSS custom properties

#### Scenario: Typography tokens are available
- **WHEN** frontend styles need headings, body copy, or labels
- **THEN** the shared tokens define Bodoni Moda headline styles and Roboto body/label styles with the reference sizes, weights, line heights, and letter spacing

#### Scenario: Spacing and shape tokens are available
- **WHEN** frontend styles need layout spacing or component shapes
- **THEN** the shared tokens define the reference spacing scale, mobile and desktop margins, gutters, and rounded radii including pill-shaped controls

#### Scenario: Surface and elevation tokens are available
- **WHEN** frontend styles need visual hierarchy
- **THEN** they use tonal surface, outline, and ambient shadow tokens instead of heavy arbitrary shadows or untracked colors

### Requirement: Fotosíntesis brand naming
The frontend SHALL use `Fotosíntesis` as the user-facing product name.

#### Scenario: App metadata uses the product name
- **WHEN** the app root metadata is rendered
- **THEN** the title and description use `Fotosíntesis` rather than `Fotosintesis AI`, `PlantCare`, or other placeholder product names

#### Scenario: User-facing brand copy uses the product name
- **WHEN** frontend UI shows the product or app name
- **THEN** the visible copy uses `Fotosíntesis` with the accent

#### Scenario: Technical identifiers remain compatible
- **WHEN** filenames, route names, capability IDs, CSS identifiers, or package identifiers require ASCII-safe text
- **THEN** they may use unaccented technical identifiers without changing user-facing copy

### Requirement: Reference placeholder adaptation
The frontend SHALL adapt static reference mockups before implementation so placeholder product copy does not ship.

#### Scenario: PlantCare appears in a reference mockup
- **WHEN** a static mockup or generated reference contains `PlantCare`
- **THEN** implementation replaces it with `Fotosíntesis` or context-specific Spanish copy before exposing it to users

#### Scenario: Placeholder copy conflicts with real product behavior
- **WHEN** a reference mockup contains copy that does not match the implemented feature or current product capability
- **THEN** implementation preserves the visual intent but rewrites the copy to accurately describe the existing Fotosíntesis flow

### Requirement: Font loading
The frontend SHALL load Bodoni Moda and Roboto through the app-level font loading mechanism and expose them to global styles.

#### Scenario: Root layout configures fonts
- **WHEN** the frontend app shell renders
- **THEN** Bodoni Moda and Roboto are loaded with the weights required by the reference typography and are exposed as CSS font variables

#### Scenario: Global styles apply the font pair
- **WHEN** base document and component styles render
- **THEN** Roboto is used for body and functional text while Bodoni Moda is available for headings and page titles

### Requirement: Icon strategy
The frontend SHALL use a consistent reference-style botanical/material icon strategy.

#### Scenario: Icons use visual-system colors
- **WHEN** shared or feature UI renders botanical/material icons
- **THEN** icons use primary green by default, secondary brown for callouts, and semantic error color only for destructive or error states

#### Scenario: Icons are sourced consistently
- **WHEN** a feature needs a new reference-style icon
- **THEN** the icon is added through the shared icon strategy rather than embedded ad hoc inside the feature screen

#### Scenario: Icon accessibility is defined
- **WHEN** an icon is decorative
- **THEN** it is hidden from assistive technology
- **WHEN** an icon communicates information not present in nearby text
- **THEN** it has an accessible label

### Requirement: Shared UI primitives
The frontend SHALL provide shared UI primitives for the Fotosintesis foundation.

#### Scenario: Button primitive is available
- **WHEN** a user-facing action is implemented or redesigned
- **THEN** it can use a shared button primitive with primary, secondary, outline or ghost, and destructive/error styling as needed

#### Scenario: Card primitive is available
- **WHEN** content needs grouped presentation
- **THEN** it can use a shared card primitive with tonal, outlined, quiet, or elevated surface treatments based on the visual-system tokens

#### Scenario: Field primitive is available
- **WHEN** forms render labels, controls, help text, or errors
- **THEN** they can use a shared field primitive with tokenized filled surfaces, outlines, focus states, and accessible error text

#### Scenario: Chip primitive is available
- **WHEN** UI renders categories, statuses, tags, or compact metadata
- **THEN** it can use a shared pill-shaped chip primitive based on tertiary or semantic container tokens

#### Scenario: Notice primitive is available
- **WHEN** UI renders informational, success, warning, or error feedback
- **THEN** it can use a shared notice primitive with tokenized container and text colors

#### Scenario: Page header primitive is available
- **WHEN** feature pages are redesigned later
- **THEN** they can use a shared page header primitive for eyebrow text, title, description, actions, and optional botanical art or icon slots

#### Scenario: Image card primitive is available
- **WHEN** plant imagery, identification imagery, or garden imagery is presented
- **THEN** it can use a shared image card primitive with rounded image treatment, fallback surface, caption, and metadata chip support

### Requirement: Responsive visual rules
The frontend SHALL define responsive visual rules for later Fotosintesis screen redesigns.

#### Scenario: Mobile layout follows the reference grid
- **WHEN** a screen is redesigned for mobile
- **THEN** it follows a 4-column rhythm with 16px outer margins and 16px gutters

#### Scenario: Desktop layout follows the reference grid
- **WHEN** a screen is redesigned for desktop
- **THEN** it follows a 12-column rhythm with 32px outer margins and 24px gutters

#### Scenario: Section spacing remains breathable
- **WHEN** a page contains major content sections
- **THEN** vertical spacing uses the shared large or extra-large spacing tokens rather than cramped arbitrary spacing

#### Scenario: Foundation change avoids screen redesigns
- **WHEN** this change is implemented
- **THEN** individual feature screens are not redesigned except for minimal integration required to prove the shared foundation works
