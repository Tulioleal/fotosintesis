## MODIFIED Requirements

### Requirement: Image receipt and storage

The backend SHALL validate received images, persist metadata and write files to object storage. Image validation failures and upload errors SHALL be surfaced to the user in English.

#### Scenario: Valid image received

- **WHEN** the backend receives a valid identification image
- **THEN** it stores the file in object storage and records path, mime type, size and relevant metadata

#### Scenario: Invalid image upload surfaces English error

- **WHEN** the backend rejects an image upload because the file is missing, empty, oversized or of an unsupported mime type
- **THEN** the system returns a 4xx error whose user-facing message is in English and identifies the specific validation cause

### Requirement: MaaS visual candidates

The system SHALL use the vision provider interface to return up to three possible plant candidates with visible traits and qualitative confidence. Vision analysis failures and inability-to-identify responses SHALL be surfaced to the user in English.

#### Scenario: MaaS returns candidates

- **WHEN** a usable image is analyzed
- **THEN** the system shows possible matches with common name, suggested scientific name, visible traits and confidence high, medium, low or inconclusive

#### Scenario: Vision analysis failure surfaces English error

- **WHEN** the vision provider fails, times out, returns an unusable response, or cannot identify a plant in the image
- **THEN** the system returns an English user-facing error that explains the issue, identifies that identification could not be completed, and offers retry, better photo guidance or manual search

#### Scenario: Candidate match copy is English

- **WHEN** a usable image is analyzed and the system returns up to three candidates
- **THEN** each candidate's `possible_match_copy` is an English sentence in the form `"Possible match, not definitive. Confidence {confidence}; confirm after reviewing visible traits and GBIF taxonomy."`

### Requirement: Identification sad paths

The system SHALL handle low confidence, no plant, blurry image, MaaS unavailable and no GBIF match as recoverable states. All user-facing messages for these recoverable states SHALL be in English.

#### Scenario: No reliable candidate

- **WHEN** the image cannot produce a reliable validated candidate
- **THEN** the system explains the issue in English and offers retry, better photo guidance or manual search
