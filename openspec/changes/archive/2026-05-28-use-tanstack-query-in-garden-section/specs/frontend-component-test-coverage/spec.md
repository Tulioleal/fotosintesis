## ADDED Requirements

### Requirement: Garden query component tests
The system SHALL include component tests for garden query-backed list and detail states.

#### Scenario: Garden list loading state is tested
- **WHEN** frontend component tests run while the garden list query is pending
- **THEN** they verify `GardenList` renders the user-facing garden loading state

#### Scenario: Garden list empty state is tested
- **WHEN** frontend component tests run with an empty successful garden list response
- **THEN** they verify `GardenList` renders empty garden guidance and the identify link

#### Scenario: Garden list search is tested
- **WHEN** a user submits a garden search in component tests
- **THEN** they verify `GardenList` requests results for the submitted search text through the garden query path

#### Scenario: Garden detail error state is tested
- **WHEN** frontend component tests run with a failed garden detail query
- **THEN** they verify `GardenDetail` renders the user-facing error state

### Requirement: Garden mutation component tests
The system SHALL include component tests for garden save and delete mutation states.

#### Scenario: Garden save success is tested
- **WHEN** a user submits the save form for a confirmed plant in component tests
- **THEN** they verify `PlantProfileView` calls the garden save mutation and renders the saved confirmation message

#### Scenario: Garden save failure is tested
- **WHEN** the garden save mutation fails in component tests
- **THEN** they verify `PlantProfileView` renders the user-facing save error

#### Scenario: Garden delete conflict is tested
- **WHEN** the garden delete mutation returns a reminder-confirmation conflict in component tests
- **THEN** they verify `GardenDetail` renders the confirmation action before retrying deletion with confirmation

#### Scenario: Garden delete success is tested
- **WHEN** the garden delete mutation succeeds in component tests
- **THEN** they verify `GardenDetail` completes the delete flow and navigates back to Mi Jardin
