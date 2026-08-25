## ADDED Requirements

### Requirement: Enforced profiles reject zero thresholds

An enforced evaluation profile MUST NOT contain a `0.0` threshold value: each gated metric is either explicitly configured above zero or omitted from the profile. Loading a profile containing a zero-valued threshold SHALL fail with an explicit configuration error identifying the offending metric.

#### Scenario: Zero thresholds are invalid configuration

- **WHEN** an evaluation profile declares any threshold equal to `0.0`
- **THEN** profile loading fails with an explicit error naming the metric
- **AND** the runner does not start a run with that profile

#### Scenario: Omitted metrics contribute nothing silently

- **WHEN** a profile omits a metric threshold entirely
- **THEN** that metric is reported as observed-but-ungated in the run report
- **AND** it does not affect approval

## MODIFIED Requirements

### Requirement: Complete approval thresholds are applied

The evaluation runner SHALL apply every configured per-case and aggregate approval threshold for text, retrieval, tool, and judge metrics from observed data. Approval SHALL require all configured required thresholds to pass.

#### Scenario: All configured thresholds are enforced

- **WHEN** a case or run completes with observed scores
- **THEN** the runner evaluates every threshold configured for the selected evaluation profile
- **AND** approval fails when any required threshold is not met

#### Scenario: A single missed threshold fails approval

- **WHEN** all thresholds pass except one required retrieval threshold
- **THEN** the case or run is marked failed with that threshold reported
