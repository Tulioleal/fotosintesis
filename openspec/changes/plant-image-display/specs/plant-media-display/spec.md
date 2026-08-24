## ADDED Requirements

### Requirement: Owner-authenticated media serving

The system SHALL serve plant media only through an authenticated route that verifies the requester owns the referenced plant and that the requested storage path belongs to one of that owner's identification image records. Object storage SHALL NOT be exposed as a public or shared static mount. Responses SHALL use the stored content type and private, non-shareable caching headers.

#### Scenario: Owner requests their plant image

- **WHEN** an authenticated owner requests the image of their garden plant
- **THEN** the backend streams the stored object with the persisted MIME type
- **AND** the response carries private, non-shareable cache headers

#### Scenario: Another user's image is requested

- **WHEN** an authenticated user requests an image belonging to another user's plant or identification record
- **THEN** the system responds with not-found behavior indistinguishable from a missing image
- **AND** it logs the rejection without image content

### Requirement: Session-authenticated frontend delivery

The frontend SHALL retrieve plant media through its authenticated backend-for-frontend proxy so browser requests carry the app session and never raw storage credentials or bucket paths.

#### Scenario: Browser loads a plant image

- **WHEN** a frontend surface renders a plant image from a storage-relative path
- **THEN** the request flows through the authenticated proxy route to the backend media route
- **AND** storage credentials and internal storage layout are not exposed to the client

### Requirement: Identification image links at save time

Saving a confirmed plant to the garden SHALL accept an optional reference to the identification image used for identification, SHALL validate server-side that the referenced path belongs to the caller and to the confirmed candidate context, and SHALL persist it as the garden plant's image path within the save transaction. Client-supplied paths that fail validation SHALL be rejected with an English message.

#### Scenario: Save links the identification photo

- **WHEN** a user saves a confirmed plant from an identification flow that produced an image
- **THEN** the garden plant row stores that identification's storage path
- **AND** subsequent reads expose the image path to authorized surfaces

#### Scenario: Foreign or arbitrary path is rejected

- **WHEN** a save request references a storage path not owned by the caller or unrelated to the candidate
- **THEN** the system rejects the save reference with an English validation error
- **AND** no image path is persisted

### Requirement: Display across garden surfaces

Surfaces that present garden plants — garden list, garden detail, home dashboard, and plant profile — SHALL display the plant's saved image when present and a neutral placeholder when absent. Absent images MUST NOT render as broken images or substitute another plant's photo.

#### Scenario: Plant with saved image

- **WHEN** a garden plant has an image path
- **THEN** garden list, garden detail, home dashboard, and plant profile render that image through the authenticated media path

#### Scenario: Plant without image

- **WHEN** a garden plant has no image path, including plants saved from manual search
- **THEN** every surface renders the shared neutral placeholder treatment

### Requirement: Single-image scope

Phase 1 associates at most one image with a garden plant: the photo from the identification that produced the confirmed candidate. Galleries, additional uploads, replacement flows, and historical image versions are out of scope until a later change extends this capability.

#### Scenario: Second image is not accepted

- **WHEN** a save request arrives for a plant that already has an image path, or a payload carries multiple image references
- **THEN** the system keeps the existing single-image association semantics
- **AND** no gallery structure is implied by the API surface

### Requirement: Deletion decouples display without orphaning ownership

Deleting a garden plant SHALL remove its image link with the plant row. The underlying identification image record and object remain governed by the identification lifecycle and are neither leaked nor deleted by garden deletion alone.

#### Scenario: Plant with image is deleted

- **WHEN** a user deletes a garden plant that displays an identification image
- **THEN** the plant and its image link are removed together
- **AND** the identification image record and object persist under identification lifecycle rules
