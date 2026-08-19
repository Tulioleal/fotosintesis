## ADDED Requirements

### Requirement: Section-level evidence fingerprints

The system SHALL associate each generated profile section with a stable section identifier, its applicable canonical aspect set, and a recorded generation version containing a deterministic evidence fingerprint and the generation policy version. The fingerprint SHALL be derived from accepted evidence identifiers and versions for the section's aspects and MUST NOT depend on retrieval order or model response formatting.

#### Scenario: Section records its evidence fingerprint

- **WHEN** a profile section is generated from accepted evidence
- **THEN** the persisted section version records the evidence fingerprint and generation policy version that produced it

#### Scenario: Fingerprint is stable across regeneration

- **WHEN** the same accepted evidence identifiers and versions are used to generate a section more than once
- **THEN** the computed fingerprint is identical

#### Scenario: Fingerprint is independent of presentation

- **WHEN** the same accepted evidence is retrieved in a different order or rendered with different formatting
- **THEN** the computed fingerprint is unchanged

### Requirement: Section-level staleness and regeneration

The system SHALL determine which profile sections depend on changed canonical aspects and SHALL mark only those sections stale when validated evidence changes. Stale sections SHALL be regenerated through durable, retryable, idempotent background work without rebuilding unaffected sections. A successful replacement SHALL swap the active section version atomically, and a failed regeneration MUST keep the previous section version readable and marked stale.

#### Scenario: New evidence affects only mapped sections

- **WHEN** accepted evidence changes for a subset of canonical aspects
- **THEN** only the profile sections mapped to those aspects are marked stale

#### Scenario: Stale section regenerates independently

- **WHEN** a stale section is regenerated through a durable job
- **THEN** unrelated profile sections and their metadata remain unchanged

#### Scenario: Successful replacement commits atomically

- **WHEN** a regenerated section is persisted successfully
- **THEN** it replaces the prior active version atomically and records its new evidence fingerprint and provenance

#### Scenario: Failed regeneration preserves the previous section

- **WHEN** regeneration of a stale section fails
- **THEN** the previous section version remains readable and is surfaced as stale with an explicit limitation

#### Scenario: Replaying a completed job does not duplicate versions

- **WHEN** a completed refresh job is replayed with the same idempotency key and fingerprint
- **THEN** no duplicate active section version is created

### Requirement: Profile freshness and refresh status

The system SHALL expose per-section freshness and refresh status so reads can identify stale, refreshing, partial, and current sections without blocking profile navigation. Status SHALL be metadata-only and MUST NOT expose raw job payloads or evidence content.

#### Scenario: Profile identifies section freshness

- **WHEN** an authenticated owner reads a profile whose sections have differing freshness
- **THEN** the response identifies which sections are stale, refreshing, partial, or current

#### Scenario: Status excludes internal details

- **WHEN** profile freshness and refresh status are returned
- **THEN** raw job payloads and evidence content are excluded

### Requirement: Legacy profile reconciliation

The system SHALL treat profiles without evidence fingerprints as unknown rather than automatically current. A reconciliation process SHALL evaluate their sections against current evidence coverage, prioritize sections containing insufficient-evidence fallback text for refresh, and SHALL keep existing sourced sections visible until a replacement succeeds. Reconciliation MUST NOT discard historical profile text or provenance.

#### Scenario: Legacy profile with insufficient sections is reconciled

- **WHEN** a profile predates evidence fingerprints and contains insufficient-evidence fallback sections
- **THEN** reconciliation marks those sections stale for refresh while keeping their current text visible

#### Scenario: Legacy sourced section remains visible until replacement

- **WHEN** a legacy profile has a sourced section without a fingerprint
- **THEN** the section remains visible and unchanged until a regenerated replacement commits

#### Scenario: Historical text is preserved

- **WHEN** reconciliation evaluates a legacy profile
- **THEN** historical profile text and provenance are not discarded
