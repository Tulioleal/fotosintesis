## Purpose

TBD - Created by syncing change `add-plant-identification-taxonomy`.
## Requirements
### Requirement: Image capture and upload

The system SHALL allow users to take a photo or upload an image to start assisted plant identification.

#### Scenario: Camera permission rejected

- **WHEN** the user rejects camera permission
- **THEN** the system explains the limitation and offers image upload from the device

### Requirement: Image receipt and storage

The backend SHALL decode, validate, and normalize received identification images before analysis or durable storage, and SHALL persist normalized metadata and write normalized files to object storage. Image validation failures and upload errors SHALL be surfaced to the user in English. A stored object SHALL be deleted when its database record cannot be persisted.

#### Scenario: Valid image received

- **WHEN** the backend receives a valid identification image that decodes successfully and stays within configured limits
- **THEN** it normalizes the image to the supported output format with orientation applied and metadata stripped
- **AND** it stores the normalized file in object storage and records the derived path, MIME type, byte size, and pixel dimensions

#### Scenario: Invalid image upload surfaces English error

- **WHEN** the backend rejects an image upload because the file is missing, empty, oversized, of an unsupported declared type, or cannot be decoded as a supported image
- **THEN** the system returns a 4xx error whose user-facing message is in English and identifies the specific validation cause

#### Scenario: Declared MIME type does not match decoded bytes

- **WHEN** an upload declares an allowed MIME type but its bytes do not decode to a supported image format
- **THEN** the system rejects the upload before object storage or provider calls
- **AND** the returned error identifies that the file is not a valid supported image

#### Scenario: Corrupt or truncated image

- **WHEN** an upload contains corrupt or truncated image data
- **THEN** the system rejects the upload before object storage or provider calls

#### Scenario: Dimensions or pixel count exceed limits

- **WHEN** a decodable image has a width, height, or total pixel count above the configured limits, even when its compressed byte size is small
- **THEN** the system rejects the upload before object storage or provider calls

#### Scenario: Decompression-bomb behavior is rejected

- **WHEN** decoding would expand an upload beyond the safe decoder limits
- **THEN** the system treats the decoder warning or error as a validation failure and rejects the upload before object storage or provider calls

#### Scenario: Persisted object uses normalized output

- **WHEN** an image is accepted
- **THEN** the stored bytes use the configured output format with orientation applied and EXIF and other unnecessary metadata removed
- **AND** the persisted MIME type and dimensions are derived from the normalized output rather than the declared upload

#### Scenario: Stored object is compensated after persistence failure

- **WHEN** object storage succeeds but persisting the image record fails
- **THEN** the backend attempts to delete the newly stored object
- **AND** a failed cleanup is logged with the object identifier but not the image content

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

### Requirement: Binomial-aware identification presentation

The identification UI SHALL use a concise binomial name for candidate display and assistant navigation when a common name is unavailable, while preserving the full scientific name as secondary taxonomic context.

#### Scenario: Binomial name used as primary candidate text

- **WHEN** an identification candidate has no common name and has a binomial name
- **THEN** the frontend renders the binomial name as the candidate's primary display text

#### Scenario: Scientific name shown only when distinct

- **WHEN** an identification candidate has a full scientific name that differs from the primary display text
- **THEN** the frontend renders the full scientific name as secondary candidate context

#### Scenario: Candidate display falls back without binomial name

- **WHEN** an identification candidate has no common name and no binomial name
- **THEN** the frontend falls back to the accepted scientific name or suggested scientific name for candidate display

#### Scenario: Assistant link includes separated plant context

- **WHEN** the user navigates from an identification candidate to the assistant
- **THEN** the frontend includes separated `plant`, `binomial` and `scientific` query parameters when those values are available

### Requirement: GBIF taxonomy validation

The system SHALL validate and normalize candidate scientific names against GBIF Species API before definitive use.

#### Scenario: Candidate validated by GBIF

- **WHEN** GBIF normalizes a candidate name
- **THEN** the system persists stable identifier, accepted name, synonyms, genus, family, species metadata, and optional binomial name without losing the original scientific identification context

#### Scenario: GBIF provides canonical name

- **WHEN** GBIF returns a reliable canonical name for a validated candidate
- **THEN** the system persists and returns that value as `binomial_name`

#### Scenario: GBIF omits reliable binomial name

- **WHEN** GBIF does not provide a reliable canonical name and genus plus species are incomplete
- **THEN** the system persists and returns `binomial_name` as null while retaining the available taxonomic fields

### Requirement: Confirmation gate

The system MUST block definitive profile generation, garden save and associated reminders until the user confirms a taxonomically validated candidate. Successful confirmation SHALL persist confirmation, one new enrichment run or reuse of equivalent active work, and the owner's candidate association for the current enrichment policy in the same successful workflow boundary. Confirmation MUST NOT succeed when durable scheduling is unavailable.

#### Scenario: Unconfirmed candidate action

- **WHEN** a user attempts a definitive action with an unconfirmed or unvalidated candidate
- **THEN** the system blocks the action and asks for confirmation or manual correction

#### Scenario: Profile generation requires confirmed candidate context

- **WHEN** a user attempts to generate or retrieve a definitive plant profile by scientific name without a confirmed validated candidate context
- **THEN** the system blocks profile access and requires confirmation of a validated candidate

#### Scenario: Validated candidate is confirmed
- **WHEN** a user confirms a candidate with validated composite taxonomy identity
- **THEN** confirmation, durable enrichment scheduling, and the owner/candidate association for the current policy become observable in the same successful workflow boundary
- **AND** the response includes metadata needed to observe enrichment without waiting for execution

#### Scenario: Confirmation workflow cannot schedule enrichment
- **WHEN** confirmation, durable scheduling, or association persistence cannot complete successfully
- **THEN** the system returns temporary unavailability or the applicable failure
- **AND** does not expose or persist the new confirmation without its durable job and association

#### Scenario: Candidate lacks valid enrichment identity
- **WHEN** validation supplies neither accepted GBIF key nor normalized binomial
- **THEN** the system does not schedule enrichment for that candidate

#### Scenario: Equivalent active enrichment exists
- **WHEN** confirmation resolves to `pending` or `processing` work with the same composite identity and policy
- **THEN** the system reuses the active job
- **AND** persists the owner's candidate-policy association

#### Scenario: Confirmation is replayed under the current policy
- **WHEN** the candidate already has an association for the current policy version
- **THEN** the system returns that association
- **AND** does not create another run

#### Scenario: Candidate association belongs to an older policy
- **WHEN** confirmation is processed under a newer policy and the candidate has no association for that version
- **THEN** the system creates or joins enrichment for the newer policy
- **AND** preserves the older policy association

#### Scenario: Prior equivalent job is terminal
- **WHEN** eligible confirmation has no current-policy association and prior equivalent jobs are `complete`, `partial`, or `failed`
- **THEN** prior terminal jobs do not block a new enrichment run

### Requirement: Identification sad paths

The system SHALL handle low confidence, no plant, blurry image, MaaS unavailable and no GBIF match as recoverable states. All user-facing messages for these recoverable states SHALL be in English.

#### Scenario: No reliable candidate

- **WHEN** the image cannot produce a reliable validated candidate
- **THEN** the system explains the issue in English and offers retry, better photo guidance or manual search

### Requirement: Gemini-backed plant vision compatibility

The system SHALL allow the vision provider interface to be backed by Gemini while preserving the existing plant identification candidate contract.

#### Scenario: Gemini vision returns plant candidates

- **WHEN** a usable identification image is analyzed with the configured vision provider set to Gemini
- **THEN** the backend returns up to three possible plant candidates with common name, suggested scientific name, visible traits and confidence high, medium, low or inconclusive

#### Scenario: Gemini vision output uses internal result types

- **WHEN** Gemini produces a structured plant-identification response
- **THEN** the provider maps the response into the existing internal image analysis result and plant candidate types without exposing Gemini SDK response types to identification domain code

