## MODIFIED Requirements

### Requirement: Evaluation dataset and runner

The system SHALL include an evaluation dataset format, an initial 50-case seed and a runner for target MVP flows. Run approval SHALL define its aggregate pass-rate denominator as the supported cases only. Each evaluation profile SHALL configure a minimum supported-case ratio, and a run whose supported share falls below that ratio SHALL fail as a coverage failure independent of scores.

#### Scenario: Pass rate uses supported cases as denominator

- **WHEN** a run completes with passing cases, failing cases, and unsupported cases
- **THEN** the aggregate pass rate divides passing supported cases by total supported cases
- **AND** unsupported cases appear only as reconciled exclusions with reasons

#### Scenario: Dataset shrinkage fails the run

- **WHEN** the supported-case ratio falls below the profile's configured minimum
- **THEN** the run fails with an explicit coverage failure naming the ratio and the unsupported reasons
- **AND** no approval verdict based on scores is emitted

### Requirement: Evaluation report

The system SHALL persist runs, scores, failures and per-flow summaries and generate a final evaluation report. Each executed run SHALL retain its report and machine-readable results as versioned artifacts under a runs directory.

#### Scenario: Run artifacts are retained

- **WHEN** a run completes in any mode
- **THEN** the runner writes `report.md` and a machine-readable result file for that run id under the runs directory
- **AND** retention of historical run directories is bounded by configured policy
