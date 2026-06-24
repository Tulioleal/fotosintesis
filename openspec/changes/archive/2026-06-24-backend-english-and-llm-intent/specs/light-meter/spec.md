## MODIFIED Requirements

### Requirement: Light measurement persistence

The system SHALL persist light measurements and allow optional association to a plant in My Garden. Light measurement error responses SHALL be surfaced to the user in English.

#### Scenario: Measurement associated to plant

- **WHEN** the user saves a measurement and selects a garden plant
- **THEN** the system stores the measurement associated with that plant for future context

#### Scenario: Light measurement request rejected with English error

- **WHEN** a light measurement request is rejected because the payload is missing, the sensor value is out of range, the garden plant does not belong to the user, or the storage layer fails
- **THEN** the system returns a 4xx or 5xx error whose user-facing message is in English and identifies the specific failure cause
