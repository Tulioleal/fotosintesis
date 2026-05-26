## ADDED Requirements

### Requirement: Image capture and upload

The system SHALL allow users to take a photo or upload an image to start assisted plant identification.

#### Scenario: Camera permission rejected

- **WHEN** the user rejects camera permission
- **THEN** the system explains the limitation and offers image upload from the device

### Requirement: Image receipt and storage

The backend SHALL validate received images, persist metadata and write files to object storage.

#### Scenario: Valid image received

- **WHEN** the backend receives a valid identification image
- **THEN** it stores the file in object storage and records path, mime type, size and relevant metadata

### Requirement: MaaS visual candidates

The system SHALL use the vision provider interface to return up to three possible plant candidates with visible traits and qualitative confidence.

#### Scenario: MaaS returns candidates

- **WHEN** a usable image is analyzed
- **THEN** the system shows possible matches with common name, suggested scientific name, visible traits and confidence high, medium, low or inconclusive

### Requirement: GBIF taxonomy validation

The system SHALL validate and normalize candidate scientific names against GBIF Species API before definitive use.

#### Scenario: Candidate validated by GBIF

- **WHEN** GBIF normalizes a candidate name
- **THEN** the system persists stable identifier, accepted name, synonyms, genus, family and species metadata

### Requirement: Confirmation gate

The system MUST block definitive profile generation, garden save and associated reminders until the user confirms a taxonomically validated candidate.

#### Scenario: Unconfirmed candidate action

- **WHEN** a user attempts a definitive action with an unconfirmed or unvalidated candidate
- **THEN** the system blocks the action and asks for confirmation or manual correction

### Requirement: Identification sad paths

The system SHALL handle low confidence, no plant, blurry image, MaaS unavailable and no GBIF match as recoverable states.

#### Scenario: No reliable candidate

- **WHEN** the image cannot produce a reliable validated candidate
- **THEN** the system explains the issue and offers retry, better photo guidance or manual search
