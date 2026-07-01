## MODIFIED Requirements

### Requirement: Home mobile-first
The system SHALL show an authenticated Home dashboard with access to identification, search, light meter, reminders, My Garden and assistant. The Home presentation SHALL follow the Fotosíntesis dashboard mosaic reference while preserving the `GET /home/summary` API flow and the English `HomeAccessItem.label` backend contract.

#### Scenario: Home opens for authenticated user
- **WHEN** an authenticated user opens `/home`
- **THEN** the system fetches `GET /home/summary`
- **AND** shows a Fotosíntesis dashboard with a welcome section, primary identification CTA, quick-access mosaic, secondary feature access, and bottom navigation with the active Home section

#### Scenario: Home summary contract
- **WHEN** Home data loads successfully
- **THEN** the response includes the authenticated user, empty-state information and access metadata for identification, search, light meter, reminders, My Garden and assistant
- **AND** the `HomeAccessItem.label` values for these access entries are in English: `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, `Assistant`

#### Scenario: Home server state
- **WHEN** the frontend fetches Home data
- **THEN** it uses TanStack Query for loading, cache, retry and error state

## ADDED Requirements

### Requirement: Home dashboard mosaic presentation
The Home dashboard SHALL adapt the dashboard mosaic reference into the Fotosíntesis product UI without changing protected route behavior or backend data flow.

#### Scenario: Reference layout is adapted to Fotosíntesis
- **WHEN** Home renders successfully
- **THEN** the page visually follows `frontend/REFERENCES/dashboard_mosaic_edition/screen.png` and `frontend/REFERENCES/dashboard_mosaic_edition/code.html` for welcome spacing, quick-access mosaic cards, botanical surfaces, rounded cards, and featured content rhythm
- **AND** placeholder reference product copy such as `PlantCare` is not exposed to users

#### Scenario: Existing Home states remain available
- **WHEN** Home is loading, empty, errored, or retrying
- **THEN** the redesigned dashboard preserves the existing loading skeleton, empty guidance, recoverable error explanation, and retry action behavior

#### Scenario: Home access remains testable
- **WHEN** automated tests query Home primary actions and navigation by accessible name
- **THEN** the implementation preserves existing accessible names unless a requirement in this change explicitly updates the user-facing copy
