## ADDED Requirements

### Requirement: Home navigation labels are English

The home-screen access labels exposed through the backend `GET /home/summary` API SHALL be in English. The six access labels are `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, and `Assistant`. Backend services and shared DTOs that produce these labels SHALL NOT emit Spanish translations for them; any consumer that hardcoded Spanish fallbacks for these labels MUST be updated to match the English API output.

#### Scenario: Home summary returns English labels

- **WHEN** an authenticated user requests `GET /home/summary`
- **THEN** the response's `access[]` array contains entries whose `label` field uses one of the six English labels `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, or `Assistant`
- **AND** the response does not contain any Spanish translation of those labels (such as `Mi Jardín`, `Identificar planta`, `Buscar plantas`, `Medidor de luz`, `Recordatorios`, or `Asistente`)

#### Scenario: Frontend consumes English labels

- **WHEN** the frontend renders the home access grid from `GET /home/summary`
- **THEN** it uses the `label` field returned by the API directly
- **AND** it does not apply a Spanish fallback translation for these six access entries
