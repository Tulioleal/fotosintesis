## MODIFIED Requirements

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
