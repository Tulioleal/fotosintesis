## ADDED Requirements

### Requirement: Canonical profile identity metadata

The system SHALL retain accepted scientific name as profile display context and SHALL expose accepted GBIF key, normalized binomial, and canonical species key when available. New canonical profile creation SHALL converge on one profile for one canonical species identity.

#### Scenario: Accepted display name differs from binomial

- **WHEN** a confirmed candidate has an authority-bearing or infraspecific accepted name and a normalized binomial
- **THEN** the profile preserves the accepted name for display
- **AND** exposes the normalized binomial and canonical identity separately

#### Scenario: Concurrent requests create one canonical profile

- **WHEN** concurrent requests create a previously absent profile for the same canonical species
- **THEN** both requests return the same persisted canonical profile
- **AND** the unique-key race does not surface as an API failure

### Requirement: Accepted evidence for new profile snapshots

New profile snapshots SHALL select canonical evidence only when it has trusted provenance, eligible review state, accepted individual aspect support, and applicable validation provenance. Creating a new profile from current accepted evidence MUST NOT regenerate an existing profile.

#### Scenario: Canonical document has no accepted support

- **WHEN** a canonical document exists without accepted aspect support or applicable validation provenance
- **THEN** new profile generation excludes it

#### Scenario: Canonical accepted evidence exists

- **WHEN** trusted canonical evidence has accepted aspect support and validation provenance before profile creation
- **THEN** a new profile may include that evidence and its source

#### Scenario: Profile snapshot already exists

- **WHEN** enrichment later accepts evidence for a species with an existing profile
- **THEN** the existing persisted sections, sources, confidence, and limitations remain exactly unchanged

### Requirement: Bounded enrichment observation

The frontend SHALL poll active enrichment for a bounded client observation window associated with the current candidate and job. Identical active responses and lease heartbeat timestamps MUST NOT extend that window indefinitely. Terminal states SHALL stop polling, and stalled state SHALL provide a one-shot manual refresh while profile actions remain available.

#### Scenario: Active job exceeds the observation window

- **WHEN** an active job remains non-terminal through the bounded client observation window
- **THEN** automatic polling stops
- **AND** the UI shows a textual delayed-state message and manual status refresh

#### Scenario: Candidate or job changes

- **WHEN** the viewed candidate or applicable job ID changes
- **THEN** stale delayed state from the prior context is cleared
- **AND** the new context receives its own bounded observation window

#### Scenario: Manual status refresh is running

- **WHEN** the user activates manual status refresh
- **THEN** exactly one immediate refetch runs
- **AND** the control is disabled with checking text until the request settles
- **AND** focus is not moved automatically

### Requirement: Accessible enrichment outcome details

The profile SHALL expose one polite enrichment status region, alert semantics for polling errors, textual covered and missing aspect labels, and distinct user-facing text for `retry_exhausted`, `workflow_incomplete`, and `indexing_deferred` limitations.

#### Scenario: Operational partial is displayed

- **WHEN** enrichment returns an operational partial limitation
- **THEN** the UI displays limitation-specific text rather than one generic fallback

#### Scenario: Poll returns unchanged state

- **WHEN** repeated polling returns the same enrichment state
- **THEN** the UI retains one polite status region
- **AND** does not insert duplicate status nodes or move focus
