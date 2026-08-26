## ADDED Requirements

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
