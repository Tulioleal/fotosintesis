## ADDED Requirements

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
