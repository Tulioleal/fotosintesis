## Purpose

TBD - Created by syncing change `require-confirmed-profile-context`.

## Requirements

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

### Requirement: Evidence-backed plant profile

The system SHALL generate or retrieve the latest persisted plant profile snapshot for a confirmed plant and SHALL keep that snapshot available while confirmed-plant enrichment is pending, processing, partial, complete, or failed. Snapshot content and sources SHALL remain distinct from current enrichment outcomes and assistant-retrievable evidence. Existing profile sections are not required to regenerate when enrichment completes.

#### Scenario: Sufficient profile evidence

- **WHEN** evidence exists for the confirmed species
- **THEN** the system renders profile sections with references to the sources used

#### Scenario: Persisted snapshot contains evidence-backed sections
- **WHEN** the latest persisted profile snapshot contains evidence-backed sections
- **THEN** the system renders those sections with the sources used to create that snapshot

#### Scenario: Enrichment is pending or processing
- **WHEN** a user opens a profile while applicable enrichment is `pending` or `processing`
- **THEN** the system returns the latest persisted snapshot without waiting for the worker
- **AND** includes current enrichment state and applicable limitations

#### Scenario: Enrichment is partial or failed
- **WHEN** applicable enrichment finishes `partial` or `failed`
- **THEN** the system continues returning the latest persisted snapshot
- **AND** identifies bounded missing aspects or failure limitations without presenting unsupported claims as complete

#### Scenario: Enrichment completes after snapshot creation
- **WHEN** enrichment indexes evidence after the snapshot was created
- **THEN** the evidence becomes available to assistant retrieval and future profile generation or refresh behavior
- **AND** this change does not promise automatic section-level regeneration

### Requirement: Regional alias fallback

The system SHALL select plant aliases by region, country or language without requiring exact GPS.

#### Scenario: Regional alias unavailable

- **WHEN** no regional alias exists or the user has no precise location
- **THEN** the system falls back to a general common name, country or language without blocking the profile

### Requirement: Source and limitation display

The system MUST show sources, confidence and limitation messages for partial or dynamically acquired information.

#### Scenario: Partial profile

- **WHEN** profile evidence is incomplete or low confidence
- **THEN** the system avoids categorical claims and shows a limitation message

### Requirement: Garden save

The system SHALL allow saving confirmed plants to Mi Jardin with optional image and user customization.

#### Scenario: Confirmed plant saved

- **WHEN** a user saves a confirmed validated plant
- **THEN** the system creates a garden record associated with the user, plant profile and optional custom data

### Requirement: Mi Jardin management

The system SHALL allow users to list, search, view detail and delete plants in My Garden.

#### Scenario: Delete plant with active reminders

- **WHEN** the user attempts to delete a plant with active reminders
- **THEN** the system warns about the reminder impact in English and requires explicit confirmation
- **AND** if the user confirms, the system deletes the plant and cascades the deletion to the related reminders, surfacing any cascade errors in English

### Requirement: Plant profile sections and limitations are English

The system SHALL emit `PlantProfileResponse.sections` keys and `PlantProfileResponse.limitations` values in English. The section keys are `description`, `characteristics`, `conditions`, `care`, `pests`, `diseases`, and `recommendations`. The fallback text and limitation strings produced by the profile builder MUST be in English.

#### Scenario: Empty-section fallback is English

- **WHEN** a plant profile is built for a scientific name with no knowledge chunks for a given section
- **THEN** the `sections` dict for that section contains the English fallback message in the form `"Insufficient evidence for {section} of {scientific_name}."`

#### Scenario: Limitations are English

- **WHEN** a plant profile is generated with limited RAG evidence or partial confidence
- **THEN** every entry in `PlantProfileResponse.limitations` is an English sentence describing the limitation (e.g. "Profile generated with limited RAG evidence; avoid critical care decisions without reviewing additional sources." or "Partial confidence: the recommendations are presented as orientative, not categorical.")

### Requirement: Profile enrichment status

The profile experience SHALL expose metadata-only applicable enrichment state to the authenticated candidate owner and SHALL refresh that state without blocking profile navigation. Polling SHALL continue only for non-terminal states and SHALL stop at a terminal state.

#### Scenario: Profile has applicable enrichment
- **WHEN** an authenticated owner retrieves a profile through confirmed candidate context with a current-policy association
- **THEN** the response includes job identity, lifecycle, and bounded covered or missing aspects
- **AND** excludes raw job payload and evidence content

#### Scenario: Frontend observes non-terminal enrichment
- **WHEN** applicable enrichment is `pending` or `processing`
- **THEN** the frontend polls authorized enrichment status only while the state remains non-terminal
- **AND** profile navigation remains available

#### Scenario: Frontend observes terminal enrichment
- **WHEN** enrichment becomes `complete`, `partial`, or `failed`
- **THEN** the frontend stops polling
- **AND** invalidates profile status and snapshot metadata without implying regenerated sections

#### Scenario: Another owner requests status
- **WHEN** a user requests enrichment state through another owner's candidate
- **THEN** the system returns the same not-found behavior used for unknown candidate context
