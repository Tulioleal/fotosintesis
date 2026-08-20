## MODIFIED Requirements

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
