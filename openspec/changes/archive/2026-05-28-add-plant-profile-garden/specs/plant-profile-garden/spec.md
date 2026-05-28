## ADDED Requirements

### Requirement: Evidence-backed plant profile

The system SHALL generate or retrieve a plant profile using RAG evidence for a confirmed plant.

#### Scenario: Sufficient profile evidence

- **WHEN** evidence exists for the confirmed species
- **THEN** the system renders profile sections with references to the sources used

### Requirement: Regional alias fallback

The system SHALL select plant aliases by region, country or language without requiring exact GPS.

#### Scenario: Regional alias unavailable

- **WHEN** no regional alias exists or the user has no precise location
- **THEN** the system falls back to a general common name, country or language without blocking the profile

### Requirement: Source and limitation display

The system MUST show sources, confidence and limitation messages for partial or dynamically acquired information.

#### Scenario: Partial profile

- **WHEN** profile evidence is incomplete or low confidence
- **THEN** the system avoids categorical claims and shows a limitation message

### Requirement: Garden save

The system SHALL allow saving confirmed plants to Mi Jardin with optional image and user customization.

#### Scenario: Confirmed plant saved

- **WHEN** a user saves a confirmed validated plant
- **THEN** the system creates a garden record associated with the user, plant profile and optional custom data

### Requirement: Mi Jardin management

The system SHALL allow users to list, search, view detail and delete plants in Mi Jardin.

#### Scenario: Delete plant with active reminders

- **WHEN** the user attempts to delete a plant with active reminders
- **THEN** the system warns about the reminder impact and requires explicit confirmation
