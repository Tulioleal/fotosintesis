## ADDED Requirements

### Requirement: Confirmed profile access
The system SHALL generate or retrieve an evidence-backed plant profile only for an authenticated user presenting a confirmed, taxonomically validated candidate that belongs to that user.

#### Scenario: Confirmed candidate profile requested
- **WHEN** an authenticated user requests a plant profile with a candidate ID for their own confirmed and validated candidate
- **THEN** the system returns or creates the profile for the candidate's accepted scientific name, falling back to the suggested scientific name when no accepted name exists

#### Scenario: Missing profile candidate context
- **WHEN** a user requests a plant profile without a candidate ID
- **THEN** the system rejects the request and explains that a confirmed plant candidate is required

#### Scenario: Unconfirmed or unvalidated candidate profile requested
- **WHEN** an authenticated user requests a plant profile with a candidate that is not confirmed or not taxonomically validated
- **THEN** the system rejects the request without creating a profile

#### Scenario: Candidate owned by another user
- **WHEN** an authenticated user requests a plant profile with a candidate ID owned by another user
- **THEN** the system rejects the request without revealing another user's candidate details

#### Scenario: Candidate name does not match requested profile
- **WHEN** an authenticated user requests a plant profile whose scientific name does not match the confirmed candidate's accepted or suggested scientific name
- **THEN** the system rejects the request without creating or returning an unrelated profile
