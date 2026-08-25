## MODIFIED Requirements

### Requirement: Garden save

The system SHALL allow saving confirmed plants to Mi Jardin with optional image and user customization. The optional image is the identification image linked to the confirmed candidate: the save operation SHALL accept an image path only when it belongs to the caller's identification records for that candidate, and SHALL persist it as the garden plant's image path in the save transaction.

#### Scenario: Confirmed plant saved

- **WHEN** a user saves a confirmed validated plant
- **THEN** the system creates a garden record associated with the user, plant profile and optional custom data

#### Scenario: Saved plant carries its identification image

- **WHEN** the save request includes the storage path of an identification image owned by the caller for the confirmed candidate
- **THEN** the created garden plant exposes that image path to authorized reads

#### Scenario: Invalid image reference does not block saving

- **WHEN** the save request omits the image or references a path that fails ownership validation
- **THEN** the plant saves successfully without an image path when the reference was omitted
- **AND** an invalid reference returns an English validation error without creating the record
