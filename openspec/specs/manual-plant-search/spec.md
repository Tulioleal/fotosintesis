# manual-plant-search Specification

## Purpose
TBD - created by archiving change add-manual-plant-search. Update Purpose after archive.
## Requirements
### Requirement: Local plant search

Authenticated users SHALL search local plant profiles by accepted scientific name, binomial name, common name, and regional alias. Matching SHALL be database-backed textual lookup over normalized profile names and aliases, and SHALL NOT rely on keyword lists or language-specific heuristics for botanical semantics. Each result SHALL identify why it matched and whether profile evidence already exists.

#### Scenario: Scientific name search

- **WHEN** an authenticated user searches by an accepted scientific or binomial name
- **THEN** the system returns matching local plant profiles with their accepted scientific name and binomial name

#### Scenario: Common name search

- **WHEN** an authenticated user searches by a common name
- **THEN** the system returns matching local plant profiles that carry that common name

#### Scenario: Alias search

- **WHEN** an authenticated user searches by a regional alias
- **THEN** the system returns matching local plant profiles that carry that alias

#### Scenario: Result explains match and evidence

- **WHEN** a local result is returned
- **THEN** the result identifies whether it matched on scientific name, binomial, common name, or alias
- **AND** indicates whether profile evidence already exists for the plant

#### Scenario: No local result

- **WHEN** a search has no local matches
- **THEN** the system returns an empty local result set and offers the external lookup path

### Requirement: GBIF candidate fallback

The system SHALL query GBIF for taxonomic candidates when local results are absent or the user explicitly expands the search, and SHALL treat GBIF as the only external provider in this change. GBIF results SHALL be normalized through the existing taxonomy client and SHALL be presented as unconfirmed candidates, never as a definitive user plant.

#### Scenario: External expansion returns GBIF candidates

- **WHEN** the user expands search to GBIF
- **THEN** the system returns normalized candidates with accepted name, rank, family, genus, and stable key

#### Scenario: GBIF candidates remain unconfirmed

- **WHEN** a GBIF candidate is displayed
- **THEN** it is labeled as an external taxonomic candidate and is not treated as a confirmed plant until the user selects and confirms it

#### Scenario: Provider failure keeps local results usable

- **WHEN** the GBIF lookup fails
- **THEN** the system keeps any local results usable, surfaces a retryable error for the external lookup, and does not fail the whole search

### Requirement: Manual candidate creation

A user SHALL be able to create a manual candidate from a selected GBIF identity without uploading an image. The candidate SHALL record a manual-search origin, retain the query and GBIF identity, belong to the authenticated user, start unconfirmed, and SHALL NOT carry a synthetic image-analysis confidence.

#### Scenario: User selects a GBIF result

- **WHEN** the user selects a GBIF candidate
- **THEN** the system creates an unconfirmed manual candidate owned by the user with the GBIF identity, accepted name, synonyms, and taxonomic metadata
- **AND** no identification image is required or stored

#### Scenario: Manual candidate has no synthetic confidence

- **WHEN** a manual candidate is created
- **THEN** it does not receive a synthetic image-analysis confidence label

### Requirement: Manual candidate confirmation reuse

A confirmed manual candidate SHALL reuse the existing confirmation gate, enrichment scheduling, and profile and garden flows, and SHALL be subject to the same ownership and validation requirements as identification candidates.

#### Scenario: Manual candidate confirmed

- **WHEN** the user confirms a validated manual candidate
- **THEN** the system schedules the same enrichment work as an identification candidate under the existing policy and ownership checks

#### Scenario: Unvalidated manual candidate blocked

- **WHEN** the user attempts a definitive action with a manual candidate that is not taxonomically validated or not confirmed
- **THEN** the system blocks the action under the existing confirmation gate

### Requirement: Search experience and accessibility

The search experience SHALL provide loading, local-results, external-expansion, empty, and error states, SHALL clearly distinguish local records from external candidates, and SHALL be fully keyboard operable with focus management and asynchronous status announcements.

#### Scenario: Search states

- **WHEN** a user runs a search
- **THEN** the UI shows loading, local results, external expansion, empty, and error states distinctly

#### Scenario: Local and external results are distinguished

- **WHEN** local records and external GBIF candidates are shown together
- **THEN** the UI clearly labels which results are local and which are external taxonomic candidates

#### Scenario: Keyboard and status announcements

- **WHEN** a user operates search and candidate selection by keyboard
- **THEN** focus management, navigation, and asynchronous status announcements remain available

