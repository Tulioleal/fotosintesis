## ADDED Requirements

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
