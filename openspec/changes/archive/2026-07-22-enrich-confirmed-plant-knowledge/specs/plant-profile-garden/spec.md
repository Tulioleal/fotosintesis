## MODIFIED Requirements

### Requirement: Evidence-backed plant profile

The system SHALL generate or retrieve the latest persisted plant profile snapshot for a confirmed plant and SHALL keep that snapshot available while confirmed-plant enrichment is pending, processing, partial, complete, or failed. Snapshot content and sources SHALL remain distinct from current enrichment outcomes and assistant-retrievable evidence. Existing profile sections are not required to regenerate when enrichment completes.

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

## ADDED Requirements

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
