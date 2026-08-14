## ADDED Requirements

### Requirement: Authoritative confirmed candidate context

The assistant chat API SHALL accept optional confirmed candidate context. The backend SHALL resolve candidate ownership, confirmation state, taxonomy validation, accepted GBIF key, and normalized binomial server-side. Client-supplied taxonomy strings SHALL remain non-authoritative display context.

#### Scenario: Owned confirmed candidate is supplied

- **WHEN** an authenticated user sends the ID of their confirmed, taxonomically validated candidate
- **THEN** assistant graph state receives the server-resolved canonical species key, accepted GBIF key, normalized binomial, and accepted scientific display name

#### Scenario: Candidate context is unauthorized or invalid

- **WHEN** candidate context belongs to another user or is unconfirmed or unvalidated
- **THEN** the backend does not use that candidate's taxonomy for retrieval
- **AND** does not trust a client-supplied canonical replacement

### Requirement: Candidate identity precedence

Server-resolved confirmed candidate identity SHALL take precedence over garden plant matching. Garden context MAY supply canonical identity only when authoritative candidate identity is absent.

#### Scenario: Display hint matches a different garden plant

- **WHEN** candidate identity resolves species A and a display hint matches garden plant B
- **THEN** retrieval continues using species A's canonical identity
- **AND** species B cannot overwrite accepted GBIF key or normalized binomial

### Requirement: Confirmed candidate assistant handoff

Identification, profile, and garden assistant links SHALL preserve confirmed candidate ID when available, and the assistant frontend SHALL map it to the chat request contract.

#### Scenario: User opens assistant from a confirmed profile

- **WHEN** a confirmed candidate ID is available in the source view
- **THEN** the assistant URL includes that ID
- **AND** the chat request includes `confirmed_candidate_id`

#### Scenario: Legacy plant-only assistant entry

- **WHEN** no confirmed candidate ID is available
- **THEN** existing plant, binomial, and scientific-name context remains supported
