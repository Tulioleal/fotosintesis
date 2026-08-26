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

The system SHALL persist light measurements and allow optional association to a plant in My Garden. Light measurement error responses SHALL be surfaced to the user in English.

#### Scenario: Measurement associated to plant

- **WHEN** the user saves a measurement and selects a garden plant
- **THEN** the system stores the measurement associated with that plant for future context

#### Scenario: Light measurement request rejected with English error

- **WHEN** a light measurement request is rejected because the payload is missing, the sensor value is out of range, the garden plant does not belong to the user, or the storage layer fails
- **THEN** the system returns a 4xx or 5xx error whose user-facing message is in English and identifies the specific failure cause

### Requirement: Persisted reading suitability for recommendation use

The system SHALL define suitability of persisted light measurements for recommendation use through source-specific freshness thresholds and a minimum reliability threshold. A reading SHALL be eligible only when it belongs to the authenticated user and the selected garden plant, its source and units are supported by the configured policy, its reliability meets the minimum threshold, and its age is within the configured freshness threshold for its source. Camera-derived values SHALL retain their approximate designation, and manual measurements SHALL NOT be promoted beyond their recorded reliability.

#### Scenario: Fresh reliable reading is eligible

- **WHEN** a persisted reading belongs to the selected plant, uses a supported source and units, meets the reliability minimum, and is within its source freshness threshold
- **THEN** the reading is eligible for recommendation use

#### Scenario: Stale reading is ineligible

- **WHEN** a persisted reading is older than the configured freshness threshold for its source
- **THEN** the reading is excluded from recommendation use

#### Scenario: Unreliable reading is ineligible

- **WHEN** a persisted reading is marked unreliable below the configured minimum
- **THEN** the reading is excluded from recommendation use

#### Scenario: Unsupported source or units is ineligible

- **WHEN** a persisted reading uses a source or units the configured policy cannot interpret
- **THEN** the reading is excluded rather than inferred

#### Scenario: Camera reading remains approximate

- **WHEN** an eligible camera-derived reading is used
- **THEN** it retains its approximate designation and is not presented as precise
