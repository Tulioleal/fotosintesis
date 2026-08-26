## ADDED Requirements

### Requirement: Semantic light context relevance

The multilingual classifier contract SHALL include a bounded, schema-validated light-context relevance signal indicating whether a plant-care request can materially benefit from a recent light measurement. Relevance SHALL be decided semantically by the classifier for applicable care topics such as watering, location, growth, stress, diagnosis, and recovery. Semantic relevance MUST NOT be implemented with hardcoded language keywords, translated word lists, regexes, or substring rules. Classifier failure SHALL follow the existing conservative fallback and clarification rules, and a non-relevant request SHALL NOT trigger a light-measurement lookup.

#### Scenario: Relevant care request signals light relevance

- **WHEN** a user asks a plant-care question whose answer can materially benefit from a recent light measurement for the selected plant
- **THEN** the schema-validated classifier output signals that light context is relevant
- **AND** the assistant proceeds to evaluate plant-specific light context

#### Scenario: Irrelevant request does not signal light relevance

- **WHEN** a user asks a plant-care question where light cannot affect the answer
- **THEN** the classifier output does not signal light relevance
- **AND** the assistant does not perform a light-measurement lookup

#### Scenario: Classifier failure does not speculate

- **WHEN** the classifier fails, times out, or returns invalid output after the existing repair and fallback rules
- **THEN** the assistant does not perform a speculative light-measurement lookup
- **AND** follows the existing conservative clarification or fallback behavior

### Requirement: Owner- and plant-scoped light context retrieval

When light context is relevant, the assistant SHALL query only light measurements associated with the authenticated user and the selected garden plant. Only an eligible measurement — one whose source and units are interpretable by the configured policy, whose reliability meets the configured minimum, and whose age is within the configured per-source freshness threshold — SHALL be treated as current and retained in assistant state.

#### Scenario: Eligible measurement is retained

- **WHEN** a relevant request finds an eligible measurement for the selected plant
- **THEN** the assistant retains that measurement in assistant state for answer context
- **AND** does not discard a successful non-empty lookup result

#### Scenario: Foreign-plant measurement is excluded

- **WHEN** a found measurement is associated with a different garden plant than the selected plant
- **THEN** the assistant does not include it in the recommendation context

#### Scenario: Stale or unreliable measurement is excluded

- **WHEN** a found measurement exceeds its source freshness threshold or falls below the reliability minimum
- **THEN** the assistant does not treat it as a current observation

### Requirement: Light-grounded synthesis and disclosure

An eligible light measurement SHALL enter answer synthesis as a contextual observation, not as universal or species-level evidence. The answer SHALL disclose the measurement date, source, reliability, and approximate status when a camera-derived value is used, and SHALL avoid categorical conclusions from one isolated reading. Species-level recommendations SHALL remain distinguishable from user measurements.

#### Scenario: Observation disclosed with provenance

- **WHEN** an eligible measurement influences a recommendation
- **THEN** the answer states when and how the reading was collected and its reliability
- **AND** explains how the reading influenced the recommendation without replacing species-level evidence

#### Scenario: Camera reading retains approximate designation

- **WHEN** a camera-derived measurement is used
- **THEN** the answer presents it as approximate rather than precise

### Requirement: Bounded light context behavior

Non-relevant requests SHALL NOT invoke the light-measurement lookup. When relevant light context is absent, stale, or unreliable and would materially limit guidance, the answer SHALL explain the limitation and recommend obtaining a new reading. When light does not affect the answer, the answer SHALL NOT mention measurement absence.

#### Scenario: Unrelated request skips lookup

- **WHEN** a request cannot be affected by light measurements
- **THEN** the assistant performs no light-measurement lookup

#### Scenario: Missing relevant context suggests remeasurement

- **WHEN** a relevant request has no eligible measurement and the absence materially limits the guidance
- **THEN** the answer explains the limitation and recommends obtaining a new reading

#### Scenario: Irrelevant absence is not disclosed

- **WHEN** light context is not relevant to the request
- **THEN** the answer does not mention that no measurement was found
