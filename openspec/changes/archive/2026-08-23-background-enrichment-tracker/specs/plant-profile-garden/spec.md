## MODIFIED Requirements

### Requirement: Profile enrichment status

The profile experience SHALL expose metadata-only applicable enrichment state to the authenticated candidate owner and SHALL refresh that state without blocking profile navigation. Polling SHALL continue only for non-terminal states and SHALL stop at a terminal state. The same owner-scoped status SHALL remain discoverable from Home and Garden, and the UI SHALL distinguish evidence enrichment from a subsequent profile refresh.

#### Scenario: Profile has applicable enrichment
- **WHEN** an authenticated owner retrieves a profile through confirmed candidate context with a current-policy association
- **THEN** the response includes job identity, lifecycle, and bounded covered or missing aspects
- **AND** excludes raw job payload and evidence content

#### Scenario: Frontend observes non-terminal enrichment
- **WHEN** applicable enrichment is `pending` or `processing`
- **THEN** the frontend polls authorized enrichment status only while the state remains non-terminal
- **AND** profile navigation remains available
- **AND** Home and Garden can display the same active work through the shared owner-scoped activity view

#### Scenario: Frontend observes terminal enrichment
- **WHEN** enrichment becomes `complete`, `partial`, or `failed`
- **THEN** the frontend stops polling that candidate status
- **AND** invalidates profile status and snapshot metadata without implying regenerated sections
- **AND** exposes the sanitized terminal outcome to the cross-page activity view

#### Scenario: Profile refresh remains distinct
- **WHEN** evidence enrichment becomes terminal and a related profile-refresh job is pending or processing
- **THEN** the profile and cross-page activity UI identify profile refresh as still active
- **AND** do not claim that all profile sections have been updated

#### Scenario: Another owner requests status
- **WHEN** a user requests enrichment state through another owner's candidate
- **THEN** the system returns the same not-found behavior used for unknown candidate context
