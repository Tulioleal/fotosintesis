## Purpose

TBD - synced from `add-light-meter`.

## Requirements

### Requirement: Sensor-first light measurement

The system SHALL attempt light measurement in this priority order: AmbientLightSensor, camera luminance fallback and manual registration.

#### Scenario: AmbientLightSensor available

- **WHEN** the browser supports AmbientLightSensor and the user grants permission
- **THEN** the system reads lux and displays a classified result

### Requirement: Camera and manual fallbacks

The system SHALL provide camera luminance and manual registration fallbacks when sensor measurement is unavailable.

#### Scenario: Camera fallback used

- **WHEN** AmbientLightSensor is unavailable but the camera can be used
- **THEN** the system estimates light from camera luminance and labels the result as approximate

### Requirement: Light classification and reliability

The system SHALL classify light as baja, media, alta or directa and record reliability metadata.

#### Scenario: Unreliable camera reading

- **WHEN** the camera is covered, overexposed or inconsistent
- **THEN** the system marks the measurement unreliable and asks the user to repeat it with guidance

### Requirement: Light measurement persistence

The system SHALL persist light measurements and allow optional association to a plant in Mi Jardin.

#### Scenario: Measurement associated to plant

- **WHEN** the user saves a measurement and selects a garden plant
- **THEN** the system stores the measurement associated with that plant for future context
