## ADDED Requirements

### Requirement: Grounded garden care summaries

The system SHALL return only sourced care data in garden list and detail responses. Garden responses SHALL NOT include static care values such as a fixed indirect-light label or a last-watering assertion when no watering events exist. Each garden plant response SHALL include a nullable next-reminder summary and a nullable latest light-measurement summary. Missing care data SHALL remain null rather than being replaced by plausible defaults.

#### Scenario: Plant without light evidence

- **WHEN** a garden plant has no persisted light measurement
- **THEN** the response's light summary is null
- **AND** the UI renders a missing-data state instead of an invented light condition

#### Scenario: Plant without watering events

- **WHEN** a garden plant has no recorded watering events
- **THEN** the response does not include a last-watering assertion
- **AND** the UI does not display a last-watering value

#### Scenario: Plant with a light measurement

- **WHEN** a garden plant has at least one persisted light measurement
- **THEN** the response's light summary exposes the latest measurement's source, classification, reliability, and observation instant

#### Scenario: Plant with a pending reminder

- **WHEN** a garden plant has at least one pending reminder
- **THEN** the response's next-reminder summary exposes the earliest pending reminder's identifier, action, due instant, and effective timezone

### Requirement: Care value provenance

A displayed care value SHALL expose a recognizable provenance category. Profile-derived guidance, sensor/camera/manual measurements, and user-provided location or notes SHALL NOT be collapsed into a single category.

#### Scenario: Profile recommendation labeled distinctly

- **WHEN** the UI displays profile-derived guidance alongside a user measurement
- **THEN** the profile guidance is labeled as evidence-backed profile recommendation and is visually distinguishable from the measurement

#### Scenario: Measurement labeled by source

- **WHEN** the UI displays a light measurement
- **THEN** it identifies the recorded source (sensor, camera, or manual) and marks camera readings as approximate
