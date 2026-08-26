## MODIFIED Requirements

### Requirement: Unsupported cases are reconciled

Evaluation cases whose expected tools or flows are absent from the current graph SHALL be corrected or marked explicitly, and SHALL NOT be scored as if their expected behavior had occurred. The count and identity of supported cases SHALL gate the run: a supported-case ratio below the configured profile minimum SHALL fail the run as a coverage failure.

#### Scenario: Case references an absent tool

- **WHEN** a dataset case declares an expected tool that the current graph does not expose
- **THEN** the runner marks the case unsupported with an explicit reason
- **AND** the case is not scored as a passing or failing quality result

#### Scenario: Supported base shrinks below the floor

- **WHEN** reconciliation leaves fewer supported cases than the profile's minimum supported-case ratio requires
- **THEN** the run is classified as a coverage failure
- **AND** the report lists every unsupported reason driving the shortfall

#### Scenario: Coverage failure is distinct from quality failure

- **WHEN** a run fails due to insufficient supported cases
- **THEN** the result distinguishes the coverage failure from threshold-based quality failures
- **AND** previously recorded score history remains comparable through the shared result schema
