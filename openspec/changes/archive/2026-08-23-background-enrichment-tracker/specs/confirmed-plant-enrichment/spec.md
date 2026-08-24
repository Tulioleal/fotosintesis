## MODIFIED Requirements

### Requirement: Owner-authorized bounded status

Each confirming owner SHALL be able to observe applicable enrichment lifecycle and bounded result metadata through direct candidate status and through an owner-scoped cross-page activity view without gaining access to another owner's candidate or raw job/evidence content. The activity view MAY include active work and terminal jobs within a bounded retention window and SHALL preserve the same metadata-only privacy boundary.

#### Scenario: Owner reads applicable status
- **WHEN** an authenticated owner requests status for their confirmed candidate and policy association
- **THEN** the system returns lifecycle, timestamps, bounded counts, covered aspects, missing aspects, and limitation categories
- **AND** excludes raw payloads, source bodies, claims, quotes, and prompts

#### Scenario: Owner reads cross-page activity
- **WHEN** an authenticated owner requests the enrichment activity view
- **THEN** the system returns their active and bounded recently terminal enrichment associations with sanitized plant/profile context
- **AND** excludes leases, worker identities, raw job payloads, and evidence content

#### Scenario: Another owner requests status
- **WHEN** a user requests enrichment status or activity through a candidate or association they do not own
- **THEN** the system returns the same not-found behavior used for an unknown candidate
