## MODIFIED Requirements

### Requirement: Confirmed profile access

The system SHALL generate or retrieve an evidence-backed plant profile only for an authenticated user presenting a confirmed, taxonomically validated candidate that belongs to that user. The system SHALL surface user-facing rejection and error messages in English.

#### Scenario: Confirmed candidate profile requested

- **WHEN** an authenticated user requests a plant profile with a candidate ID for their own confirmed and validated candidate
- **THEN** the system returns or creates the profile for the candidate's accepted scientific name, falling back to the suggested scientific name when no accepted name exists

#### Scenario: Missing profile candidate context

- **WHEN** a user requests a plant profile without a candidate ID
- **THEN** the system rejects the request in English and explains that a confirmed plant candidate is required

#### Scenario: Unconfirmed or unvalidated candidate profile requested

- **WHEN** an authenticated user requests a plant profile with a candidate that is not confirmed or not taxonomically validated
- **THEN** the system rejects the request without creating a profile and surfaces an English error message

#### Scenario: Candidate owned by another user

- **WHEN** an authenticated user requests a plant profile with a candidate ID owned by another user
- **THEN** the system rejects the request in English without revealing another user's candidate details

#### Scenario: Candidate name does not match requested profile

- **WHEN** an authenticated user requests a plant profile whose scientific name does not match the confirmed candidate's accepted or suggested scientific name
- **THEN** the system rejects the request without creating or returning an unrelated profile and surfaces an English error message

### Requirement: Mi Jardin management

The system SHALL allow users to list, search, view detail and delete plants in My Garden.

#### Scenario: Delete plant with active reminders

- **WHEN** the user attempts to delete a plant with active reminders
- **THEN** the system warns about the reminder impact in English and requires explicit confirmation
- **AND** if the user confirms, the system deletes the plant and cascades the deletion to the related reminders, surfacing any cascade errors in English

## ADDED Requirements

### Requirement: Plant profile sections and limitations are English

The system SHALL emit `PlantProfileResponse.sections` keys and `PlantProfileResponse.limitations` values in English. The section keys are `description`, `characteristics`, `conditions`, `care`, `pests`, `diseases`, and `recommendations`. The fallback text and limitation strings produced by the profile builder MUST be in English.

#### Scenario: Empty-section fallback is English

- **WHEN** a plant profile is built for a scientific name with no knowledge chunks for a given section
- **THEN** the `sections` dict for that section contains the English fallback message in the form `"Insufficient evidence for {section} of {scientific_name}."`

#### Scenario: Limitations are English

- **WHEN** a plant profile is generated with limited RAG evidence or partial confidence
- **THEN** every entry in `PlantProfileResponse.limitations` is an English sentence describing the limitation (e.g. "Profile generated with limited RAG evidence; avoid critical care decisions without reviewing additional sources." or "Partial confidence: the recommendations are presented as orientative, not categorical.")
