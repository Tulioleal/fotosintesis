## ADDED Requirements

### Requirement: Evidence-change signals after accepted ingestion

The system SHALL emit an evidence-change signal after accepted evidence ingestion commits, describing the affected composite species identity and canonical aspects, so profile refresh can determine which sections depend on the change. The signal MUST be transactional with the accepted-ingestion commit and MUST NOT expose evidence content or raw payloads.

#### Scenario: Accepted evidence emits a change signal

- **WHEN** accepted enrichment evidence commits for a composite species
- **THEN** the system records an evidence-change signal for that species and the changed canonical aspects in the same transaction

#### Scenario: Change signal scopes to changed aspects

- **WHEN** accepted evidence supports a subset of canonical aspects
- **THEN** the change signal identifies only those changed aspects

#### Scenario: Change signal excludes evidence content

- **WHEN** an evidence-change signal is recorded
- **THEN** it contains species identity and canonical aspects without raw evidence content or job payloads

#### Scenario: Rolled-back ingestion emits no signal

- **WHEN** accepted evidence ingestion rolls back
- **THEN** no evidence-change signal becomes eligible for refresh
