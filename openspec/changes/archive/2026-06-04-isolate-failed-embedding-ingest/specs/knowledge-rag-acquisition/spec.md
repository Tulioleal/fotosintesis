## ADDED Requirements

### Requirement: Failed acquisition rolls back poisoned transactions
The system SHALL roll back failed database work before returning degraded acquisition or fallback results when best-effort knowledge ingestion, embedding persistence or vector indexing fails.

#### Scenario: Trusted acquisition persistence fails after database work starts
- **WHEN** trusted acquisition attempts to persist or index generated knowledge and the operation fails after database work has started
- **THEN** the system rolls back the failed transaction before returning a degraded acquisition result
- **AND** the same request can continue using the database session for later assistant persistence

#### Scenario: Fallback evidence persistence failure is isolated
- **WHEN** fallback web evidence ingestion fails after usable web evidence exists
- **THEN** the system reports the persistence failure as non-blocking tool failure metadata
- **AND** the failed transaction is rolled back before the assistant response is generated or saved
