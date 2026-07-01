## ADDED Requirements

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
