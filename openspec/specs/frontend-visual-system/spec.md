## Purpose

Define the shared Fotosintesis frontend visual foundation for tokens, brand naming, reference adaptation, fonts, icons, UI primitives, and responsive visual rules.

## Requirements

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
The frontend SHALL use Phosphor Icons (@phosphor-icons/react) as the shared icon source, with the `weight="fill"` style as the default to preserve the solid botanical feel.

#### Scenario: Icons use visual-system colors
- **WHEN** shared or feature UI renders icons
- **THEN** icons inherit the surrounding `color` so they pick up the Primary green by default, the Secondary brown for callouts, and the semantic error color for destructive or error states
- **AND** the tone is applied via shared SCSS tone utility classes (e.g. `tone-primary`, `tone-on-primary`) referenced as `className` on the icon component

#### Scenario: Icons are sourced consistently
- **WHEN** a feature needs an icon
- **THEN** the icon is imported from `@phosphor-icons/react` and used with the global `IconContext.Provider` defaults (color: currentColor, size: 20, weight: fill)
- **AND** stroke-style variants are produced by overriding `weight="regular"` per call site rather than introducing a separate icon set

#### Scenario: Icon accessibility is defined
- **WHEN** an icon is decorative
- **THEN** it is rendered with `aria-hidden="true"`
- **WHEN** an icon communicates information not present in nearby text
- **THEN** it is rendered with the Phosphor `alt` prop so the underlying svg gets a `<title>` element announcing the label

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

### Requirement: Authenticated shell applies Fotosíntesis foundation

The authenticated app shell and Home dashboard SHALL apply the archived Fotosíntesis visual foundation as their required design baseline.

#### Scenario: Private shell uses foundation tokens

- **WHEN** private shell styles are authored
- **THEN** they use the shared Fotosíntesis colors, typography, spacing, radius, surface, outline, and elevation tokens instead of introducing unrelated palette, type, or shadow rules

#### Scenario: Home dashboard uses foundation tokens

- **WHEN** the Home dashboard is redesigned
- **THEN** its cards, headings, labels, chips, imagery treatments, empty state, error state, and loading state use the archived Fotosíntesis visual foundation

### Requirement: Authenticated reference copy adaptation

Authenticated shell and Home UI SHALL adapt external reference copy to the Fotosíntesis product voice before exposing it to users.

#### Scenario: Placeholder product names are replaced

- **WHEN** shell or Home UI adapts a reference that contains `PlantCare` or another placeholder product name
- **THEN** visible product copy uses `Fotosíntesis`

#### Scenario: Reference copy does not override product behavior

- **WHEN** the dashboard mosaic reference includes placeholder navigation, feature, or footer copy that does not match the implemented Fotosíntesis routes
- **THEN** the implementation preserves the visual intent while using copy and destinations that match the current authenticated app

### Requirement: Public entry surfaces apply Fotosíntesis foundation

The public entry surfaces SHALL apply the archived Fotosíntesis visual foundation as their required design baseline.

#### Scenario: Public root uses welcome reference

- **WHEN** an unauthenticated or anonymous visitor opens the public root page
- **THEN** the page visually follows `frontend/REFERENCES/bienvenida_con_funcionalidades/screen.png` and `frontend/REFERENCES/bienvenida_con_funcionalidades/code.html` for editorial hero structure, botanical tonal surfaces, feature mosaic rhythm, rounded imagery/cards, clear authentication CTAs, and responsive spacing
- **AND** the page uses the shared Fotosíntesis colors, typography, spacing, radius, surface, outline, and elevation tokens

#### Scenario: Welcome route matches public entry language

- **WHEN** a visitor opens `/welcome`
- **THEN** the screen uses the same Fotosíntesis public-entry visual language as the public root while preserving its role as a route into login and registration

#### Scenario: Public entry adapts placeholder copy

- **WHEN** public-entry UI adapts a reference that contains `PlantCare`, unsupported navigation, generic footer links, or placeholder feature copy
- **THEN** visible copy uses `Fotosíntesis` and accurate current product messaging instead of exposing placeholder product names or unsupported behavior

#### Scenario: Public entry remains responsive

- **WHEN** the public root or welcome route is viewed on mobile and desktop widths
- **THEN** the layout follows the Fotosíntesis responsive margin, gutter, grid, and section-spacing rules without horizontal overflow or inaccessible fixed content

### Requirement: Authentication surfaces apply transactional Fotosíntesis foundation

The login, registration, and recovery surfaces SHALL use the transactional authentication style derived from the Fotosíntesis references.

#### Scenario: Login uses transactional reference

- **WHEN** a visitor opens `/login`
- **THEN** the screen visually follows `frontend/REFERENCES/iniciar_sesi_n/screen.png` and `frontend/REFERENCES/iniciar_sesi_n/code.html` for minimal brand header, centered card, filled tokenized fields, ambient elevation, and simple footer treatment
- **AND** it uses the shared Fotosíntesis visual-system tokens rather than unrelated colors, typography, or shadows

#### Scenario: Registration uses transactional reference

- **WHEN** a visitor opens `/register`
- **THEN** the screen visually follows `frontend/REFERENCES/crear_cuenta/screen.png` and `frontend/REFERENCES/crear_cuenta/code.html` for transactional card structure, header content, filled tokenized fields, primary action treatment, and footer treatment
- **AND** it adapts placeholder reference copy to `Fotosíntesis`

#### Scenario: Recovery uses the same transactional family

- **WHEN** a visitor opens `/forgot-password`
- **THEN** the screen uses the same Fotosíntesis transactional layout style as login and registration while preserving recovery-specific copy and form behavior

#### Scenario: Auth reference copy is adapted

- **WHEN** authentication UI adapts a reference that contains `PlantCare`, static-only social login, or placeholder legal/footer copy
- **THEN** implementation preserves the visual intent while using `Fotosíntesis`, real route destinations, disabled placeholder semantics for unavailable social login, and accurate current product copy

#### Scenario: Auth visual changes remain tokenized

- **WHEN** public or authentication styles are authored
- **THEN** they consume the archived Fotosíntesis tokens, font variables, shared primitives, and icon strategy where applicable instead of introducing a separate design foundation

### Requirement: Identification journey applies Fotosíntesis foundation

The `/identify` journey SHALL apply the archived Fotosíntesis visual foundation across its initial, camera fallback, preview, analyzing, error, results, and confirmed-candidate states while preserving the existing identification behavior.

#### Scenario: Initial identification entry follows the reference
- **WHEN** an authenticated user opens `/identify` before selecting an image
- **THEN** the screen visually follows `frontend/REFERENCES/identificando_planta_2/screen.png` and `frontend/REFERENCES/identificando_planta_2/code.html` for the page heading, breathable botanical surface, rounded upload well, dashed media drop-zone treatment, primary upload/camera actions, and responsive spacing
- **AND** the screen uses the shared Fotosíntesis colors, typography, spacing, radii, surfaces, outlines, and elevation tokens

#### Scenario: Camera fallback remains available
- **WHEN** camera access is unavailable or permission is rejected
- **THEN** the journey shows the existing camera limitation notice and offers the existing file upload fallback
- **AND** the notice is styled with Fotosíntesis notice/error surfaces without changing the fallback behavior

#### Scenario: Preview uses the selected image
- **WHEN** the user selects or captures an image
- **THEN** the journey shows a rounded preview media area using the selected image with an accessible alt text
- **AND** the preview treatment follows the identification reference family rather than introducing unrelated imagery or colors

#### Scenario: Analyzing state follows the reference
- **WHEN** the selected image is being submitted to `/api/identifications`
- **THEN** the screen visually follows `frontend/REFERENCES/identificando_planta_1/screen.png` and `frontend/REFERENCES/identificando_planta_1/code.html` for muted image preview, scanning or progress treatment, analysis status text, and candidate skeleton rhythm
- **AND** the upload still uses the existing `/api/identifications` request flow

#### Scenario: Error state stays recoverable
- **WHEN** image upload or analysis fails
- **THEN** the journey presents the existing recoverable error message in a tokenized Fotosíntesis error or notice treatment
- **AND** the user can retry by using the existing upload or camera controls

#### Scenario: Results follow the reference
- **WHEN** identification candidates are returned
- **THEN** the screen visually follows `frontend/REFERENCES/resultados_de_identificaci_n/screen.png` and `frontend/REFERENCES/resultados_de_identificaci_n/code.html` for the captured-photo area, possible-match section heading, result count/status chip, rounded candidate cards, confidence treatment, trait content, and responsive one-column to multi-column layout
- **AND** each candidate still displays the current candidate name, scientific context, visible traits, confidence, GBIF validation status, and synonyms when present

#### Scenario: Confirmation safeguards are preserved
- **WHEN** a candidate is not GBIF validated
- **THEN** its confirmation action remains blocked
- **AND** the visual treatment communicates the unavailable validation state without enabling definitive profile, garden-save, or assistant flows

#### Scenario: Confirmed candidates keep navigation links
- **WHEN** a validated candidate is confirmed
- **THEN** the journey still renders valid links to the plant profile and assistant context for that candidate
- **AND** those links keep their current route behavior and accessible names unless explicitly updated by this spec

#### Scenario: Reference copy is adapted
- **WHEN** implementation adapts copy from identification references that mention `PlantCare`, generic static navigation, or unsupported placeholder behavior
- **THEN** visible user-facing copy uses `Fotosíntesis` and accurate current product messaging instead

#### Scenario: Existing test anchors remain stable
- **WHEN** unit or e2e tests interact with upload, camera, confirmation, profile, or assistant controls
- **THEN** the accessible labels, button names, link names, and route behavior used by the existing identification tests remain stable unless the test is intentionally updated for a spec-level copy change

### Requirement: Assistant experience applies Fotosíntesis foundation

The `/assistant` experience SHALL apply the archived Fotosíntesis visual foundation to the assistant layout, plant context sidebar, message stream, composer, supporting cards, and state treatments.

#### Scenario: Desktop assistant follows reference structure

- **WHEN** an authenticated user opens `/assistant` on the desktop viewport class used for visual verification
- **AND** plant context is available
- **THEN** the assistant screen visually follows `frontend/REFERENCES/asistente_ai/screen.png` and `frontend/REFERENCES/asistente_ai/code.html` for task-focused header treatment, contextual plant sidebar, main chat area, anchored composer, rounded message bubbles, botanical tonal surfaces, typography, color, spacing, and hierarchy
- **AND** the screen uses the shared Fotosíntesis colors, typography, spacing, radii, surfaces, outlines, and elevation tokens

#### Scenario: Plant context sidebar adapts live context

- **WHEN** the assistant is opened with plant context query parameters
- **THEN** the contextual sidebar presents the plant display name or nickname and available scientific/binomial context in the reference sidebar structure
- **AND** unavailable image, location, or notes data uses neutral placeholder treatment without inventing botanical or user-specific facts

#### Scenario: Assistant without plant context remains usable

- **WHEN** the assistant is opened without plant context query parameters
- **THEN** the chat remains usable without an empty or misleading plant context sidebar
- **AND** the layout keeps the same Fotosíntesis visual language for the header, chat stream, empty state, and composer

#### Scenario: Mobile assistant avoids shell navigation conflict

- **WHEN** an authenticated user opens `/assistant` on a mobile viewport within the private shell
- **THEN** the assistant layout remains readable and operable with no horizontal overflow
- **AND** the composer remains visible or reachable without conflicting with the private shell bottom navigation

#### Scenario: Reference copy is adapted

- **WHEN** implementation adapts copy from the assistant reference that contains `PlantCare` or unsupported placeholder behavior
- **THEN** visible user-facing copy uses `Fotosíntesis` and accurate current product messaging
- **AND** route behavior and accessible names are preserved unless explicitly updated by this spec

### Requirement: Assistant visual verification state

The assistant redesign SHALL define and use a plant-context visual verification state before implementation is accepted.

#### Scenario: Visual verification state includes plant context conversation

- **WHEN** the redesigned assistant is manually compared against `frontend/REFERENCES/asistente_ai/screen.png`
- **THEN** verification uses the same viewport class as the reference screenshot
- **AND** the state includes a visible plant-context assistant session with a nickname or display name, scientific or binomial name, location or notes placeholder when live data is unavailable, at least one user message, at least one assistant message, and the composer visible

#### Scenario: Dynamic data does not justify layout drift

- **WHEN** live API data differs from the static assistant reference
- **THEN** mocked or test data approximates the reference state for visual verification where possible
- **AND** dynamic text, source, or plant metadata differences are not used to justify structural, spacing, typography, color, card shape, or hierarchy drift

#### Scenario: Intentional visual deviations are documented

- **WHEN** implementation intentionally deviates from `frontend/REFERENCES/asistente_ai/screen.png`
- **THEN** the deviation and reason are documented in the implementation verification notes or design follow-up before the change is considered complete

### Requirement: Care tools apply Fotosíntesis foundation

The `/reminders` and `/light-meter` care-tool experiences SHALL apply the archived Fotosíntesis visual foundation while preserving their existing reminder and light-meter behavior contracts.

#### Scenario: Reminders follows reference structure

- **WHEN** an authenticated user opens `/reminders` on the desktop viewport class used for visual verification
- **AND** the target reminders verification state is available
- **THEN** the reminders screen visually follows `frontend/REFERENCES/recordatorios/screen.png` and `frontend/REFERENCES/recordatorios/code.html` for page structure, split form/list layout, spacing, typography, color, form treatment, reminder list hierarchy, card treatment, action affordances, and responsive behavior
- **AND** the screen uses the shared Fotosíntesis colors, typography, spacing, radii, surfaces, outlines, icon strategy, and elevation tokens

#### Scenario: Reminders behavior is preserved

- **WHEN** the reminders screen is redesigned
- **THEN** listing reminders, creating reminders, updating reminders, completing reminders, deleting reminders, recurring reminder behavior, validation errors, notification permission messaging, and AI suggestion acceptance continue to use the existing behavior and API flows
- **AND** accessible labels, button names, form labels, route behavior, and current test anchors remain stable unless product naming or reference adaptation explicitly updates visible copy
- **AND** the new-reminder form's action input is exposed as a structured `Tipo de Tarea` select over the fixed task vocabulary `Riego | Fertilizante | Poda | Trasplante | Limpieza | Revisión general`; both the local AI suggestion builder and the assistant's reminder-suggestion acceptance path normalize their action to that vocabulary before saving, so every persisted reminder action is representable in the form on edit

#### Scenario: Light meter follows care-tool visual language

- **WHEN** an authenticated user opens `/light-meter`
- **THEN** the light meter screen visually aligns with the Fotosíntesis care-tool language through a measurement-first layout, tonal card hierarchy, tokenized action treatment, sensor/camera/manual status messaging, reliability surfaces, optional garden plant association, and save affordance
- **AND** the layout derives from the archived Fotosíntesis foundation and already-redesigned plant detail/care-action surfaces rather than introducing an unrelated visual language

#### Scenario: Light meter behavior is preserved

- **WHEN** the light meter screen is redesigned
- **THEN** AmbientLightSensor attempts, camera fallback, manual classification, reliability states, camera reliability blocking, garden plant association, and measurement persistence continue to use the existing behavior and API flows
- **AND** accessible labels, button names, route behavior, and current test anchors remain stable unless product naming or reference adaptation explicitly updates visible copy

#### Scenario: Care-tool links remain valid

- **WHEN** garden, profile, assistant, or private shell surfaces link to reminders or light meter
- **THEN** those links continue to resolve to the existing routes with the same route behavior
- **AND** unrelated garden, profile, assistant, identification, public/auth, and shell screens are not redesigned by this care-tool change except for minimal link-validity adjustments

#### Scenario: Care-tool reference copy is adapted

- **WHEN** implementation adapts copy from the reminders reference that contains `PlantCare` or unsupported placeholder behavior
- **THEN** visible user-facing copy uses `Fotosíntesis` and accurate current product messaging
- **AND** static-only reference navigation, footer, or placeholder actions are not exposed when they conflict with current app behavior

### Requirement: Care-tool visual verification states

The care-tool redesign SHALL define and use visual verification states for reminders and light meter before implementation is accepted.

#### Scenario: Reminders verification state includes required content

- **WHEN** the redesigned reminders screen is manually compared against `frontend/REFERENCES/recordatorios/screen.png`
- **THEN** verification uses the same viewport class as the reference screenshot
- **AND** the state includes at least one saved garden plant, a visible new-reminder form, visible AI suggestion content, multiple reminder rows or cards, and visible pending, completed or completion-capable, and action states where feasible

#### Scenario: Light meter verification state includes required content

- **WHEN** the redesigned light meter screen is manually verified against the derived Fotosíntesis care-tool pattern
- **THEN** the state includes the initial measurement action area, manual registration area, camera or sensor status messaging, a prepared reading result, reliability messaging, optional garden plant association when plants are available, and the save action

#### Scenario: Dynamic data does not justify layout drift

- **WHEN** live API data differs from the static reminders reference or the prepared light-meter verification state
- **THEN** test, seeded, or mocked data approximates the target verification state where possible
- **AND** dynamic text, dates, plant names, API timing, or sensor availability differences are not used to justify structural, spacing, typography, color, card shape, form treatment, hierarchy, or responsive drift

#### Scenario: Intentional care-tool visual deviations are documented

- **WHEN** implementation intentionally deviates from `frontend/REFERENCES/recordatorios/screen.png` or from the derived light-meter care-tool pattern
- **THEN** the deviation and reason are documented in the implementation verification notes or design follow-up before the change is considered complete
