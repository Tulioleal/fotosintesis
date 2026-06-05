## ADDED Requirements

### Requirement: Tool ingestion failures preserve chat persistence
The assistant SHALL keep the chat database session usable after best-effort knowledge ingestion fails inside an assistant tool and is reported as a non-blocking tool failure.

#### Scenario: Structured ingestion failure does not abort assistant response save
- **WHEN** structured plant-data evidence is available but its knowledge ingestion fails after database work has started
- **THEN** the assistant records the ingestion failure as tool failure metadata
- **AND** rolls back the failed database transaction before continuing
- **AND** saves and returns the assistant response for the chat request

#### Scenario: Web evidence ingestion failure does not abort assistant response save
- **WHEN** trusted web fallback evidence is available but fallback evidence ingestion fails after database work has started
- **THEN** the assistant records the ingestion failure as tool failure metadata
- **AND** rolls back the failed database transaction before continuing
- **AND** saves and returns the assistant response for the chat request
