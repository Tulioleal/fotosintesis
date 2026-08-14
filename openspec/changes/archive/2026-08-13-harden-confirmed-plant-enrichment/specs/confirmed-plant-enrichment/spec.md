## ADDED Requirements

### Requirement: Accepted durable enrichment progress

The system SHALL checkpoint accepted enrichment progress by job. Useful accepted coverage SHALL be the union of semantically accepted local aspects and durably persisted accepted aspects. Final semantic judge output that has not passed source binding and persistence MUST NOT by itself make a failed or exhausted job `partial`.

#### Scenario: Judge support is rejected before persistence

- **WHEN** final semantic judging reports covered aspects but every support item is rejected before persistence and no accepted local coverage exists
- **THEN** the durable checkpoint has no useful accepted coverage
- **AND** operational exhaustion produces `failed`, not `partial`

#### Scenario: Accepted evidence survives operational failure

- **WHEN** at least one required aspect has accepted local or persisted evidence before a later operational failure exhausts retries
- **THEN** the job becomes `partial`
- **AND** bounded result metadata identifies covered aspects, missing aspects, and the operational limitation

#### Scenario: Accepted evidence is not fully indexed

- **WHEN** accepted evidence persists but its vector indexing does not finish before operational exhaustion
- **THEN** the job becomes `partial` with `indexing_deferred`
- **AND** it is not reported as complete or total failure

### Requirement: Serialized progress convergence

Progress checkpoint aspect sets SHALL only grow across retries and concurrent accepted evidence operations. Read-merge-write mutations and terminal decisions MUST serialize on the progress row, while evidence and its paired checkpoint update SHALL commit in the same relational transaction.

#### Scenario: Concurrent claims accept different aspects

- **WHEN** two concurrent transactions add different accepted aspects to one enrichment checkpoint
- **THEN** the persisted checkpoint contains the union of both aspects
- **AND** neither update erases the other

#### Scenario: Checkpoint update fails

- **WHEN** a paired checkpoint update fails before an evidence transaction commits
- **THEN** the paired evidence transaction rolls back
- **AND** no evidence-only or checkpoint-only milestone remains

### Requirement: Coverage-balanced local retrieval

Local enrichment retrieval SHALL select canonical evidence candidates per requested aspect and balance the bounded result across requested aspects before semantic judging. Metadata filtering SHALL select candidates only; semantic judging SHALL remain authoritative for multilingual botanical coverage.

#### Scenario: Required aspect evidence is below a global top-k

- **WHEN** unrelated higher-scoring chunks would displace a requested aspect from a global top-k result
- **THEN** the aspect-filtered retrieval still supplies that aspect's eligible candidate to semantic judging

#### Scenario: Multiple aspects have candidates

- **WHEN** several requested aspects each have eligible candidates
- **THEN** each available aspect contributes one candidate before any aspect contributes a second
- **AND** stable chunk identities are deduplicated

### Requirement: Fetched-only confirmed enrichment evidence

Confirmed-plant enrichment SHALL send only successfully fetched trusted page content to final acquired-evidence judging and persistence. Search snippets MAY remain available to the separate degraded assistant fallback but MUST NOT create confirmed-plant documents, chunks, embeddings, aspect support, or vector nodes.

#### Scenario: Fetch fails but a search snippet exists

- **WHEN** a trusted search result has a snippet but page fetching fails, is unsafe, exceeds bounds, or returns an unsupported content type
- **THEN** the snippet does not contribute acquired enrichment coverage
- **AND** it produces no confirmed-plant persistence or vector effects

#### Scenario: Mixed fetched and snippet-only results

- **WHEN** a bounded acquisition contains successful fetched pages and snippet-only failures
- **THEN** only fetched trusted content enters final enrichment judging and persistence eligibility

### Requirement: Reconfirmation preserves explicit run semantics

Same-candidate same-policy confirmation replay SHALL return its existing association whether the associated job is active or terminal. A newer policy SHALL use a separate association. Switching to a sibling candidate MUST NOT cancel already committed species-level work.

#### Scenario: Same candidate is reconfirmed after terminal status

- **WHEN** a candidate already has a current-policy association whose job is complete, partial, or failed
- **THEN** confirmation replay returns that association
- **AND** does not silently create a rerun

#### Scenario: Candidate is confirmed under a newer policy

- **WHEN** the candidate has only an older-policy association
- **THEN** confirmation creates or joins work for the newer policy
- **AND** preserves the older association and evidence history

### Requirement: Canonical later assistant retrieval

Accepted and indexed enrichment evidence SHALL be retrievable by later assistant requests using canonical identity resolved server-side from the current user's confirmed, taxonomically validated candidate. Client taxonomy strings or canonical keys MUST NOT override that identity.

#### Scenario: Assistant opens from a confirmed profile

- **WHEN** the profile assistant link carries the confirmed candidate ID
- **THEN** the backend resolves accepted GBIF key and normalized binomial from the owned confirmed candidate
- **AND** aspect-filtered retrieval uses that canonical identity

#### Scenario: Garden display matching selects another plant

- **WHEN** a client display hint could match a different garden plant after candidate identity was resolved
- **THEN** candidate-resolved canonical identity remains authoritative
- **AND** retrieval does not combine taxonomy from different species

### Requirement: Proposal 11 remains independent

Confirmed-plant enrichment MUST NOT regenerate, invalidate, replace, version, or refresh existing persisted profile sections and MUST NOT schedule profile-refresh work.

#### Scenario: Enrichment completes for an existing profile

- **WHEN** accepted evidence is persisted and indexed after a profile snapshot already exists
- **THEN** later assistant retrieval can use the evidence
- **AND** the existing profile sections, sources, confidence, and limitations remain unchanged
- **AND** no profile-refresh job is created
