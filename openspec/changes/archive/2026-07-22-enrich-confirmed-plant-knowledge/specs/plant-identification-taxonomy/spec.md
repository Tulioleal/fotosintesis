## MODIFIED Requirements

### Requirement: Confirmation gate

The system MUST block definitive profile generation, garden save and associated reminders until the user confirms a taxonomically validated candidate. Successful confirmation SHALL persist confirmation, one new enrichment run or reuse of equivalent active work, and the owner's candidate association for the current enrichment policy in the same successful workflow boundary. Confirmation MUST NOT succeed when durable scheduling is unavailable.

#### Scenario: Unconfirmed candidate action
- **WHEN** a user attempts a definitive action with an unconfirmed or unvalidated candidate
- **THEN** the system blocks the action and asks for confirmation or manual correction

#### Scenario: Profile generation requires confirmed candidate context
- **WHEN** a user attempts to generate or retrieve a definitive plant profile by scientific name without a confirmed validated candidate context
- **THEN** the system blocks profile access and requires confirmation of a validated candidate

#### Scenario: Validated candidate is confirmed
- **WHEN** a user confirms a candidate with validated composite taxonomy identity
- **THEN** confirmation, durable enrichment scheduling, and the owner/candidate association for the current policy become observable in the same successful workflow boundary
- **AND** the response includes metadata needed to observe enrichment without waiting for execution

#### Scenario: Confirmation workflow cannot schedule enrichment
- **WHEN** confirmation, durable scheduling, or association persistence cannot complete successfully
- **THEN** the system returns temporary unavailability or the applicable failure
- **AND** does not expose or persist the new confirmation without its durable job and association

#### Scenario: Candidate lacks valid enrichment identity
- **WHEN** validation supplies neither accepted GBIF key nor normalized binomial
- **THEN** the system does not schedule enrichment for that candidate

#### Scenario: Equivalent active enrichment exists
- **WHEN** confirmation resolves to `pending` or `processing` work with the same composite identity and policy
- **THEN** the system reuses the active job
- **AND** persists the owner's candidate-policy association

#### Scenario: Confirmation is replayed under the current policy
- **WHEN** the candidate already has an association for the current policy version
- **THEN** the system returns that association
- **AND** does not create another run

#### Scenario: Candidate association belongs to an older policy
- **WHEN** confirmation is processed under a newer policy and the candidate has no association for that version
- **THEN** the system creates or joins enrichment for the newer policy
- **AND** preserves the older policy association

#### Scenario: Prior equivalent job is terminal
- **WHEN** eligible confirmation has no current-policy association and prior equivalent jobs are `complete`, `partial`, or `failed`
- **THEN** prior terminal jobs do not block a new enrichment run
