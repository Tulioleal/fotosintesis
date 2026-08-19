## ADDED Requirements

### Requirement: Metrics are computed from observed results

Evaluation metrics SHALL be computed from observed execution records produced by the assistant graph, not from reference fixtures or reference-derived candidate text.

#### Scenario: Text metrics use graph-produced candidate

- **WHEN** a referenced text evaluation computes BERTScore or ROUGE-L
- **THEN** the candidate text is the graph-produced answer
- **AND** the reference text is used only as the scoring reference

#### Scenario: Retrieval metrics use observed evidence

- **WHEN** a retrieval case computes precision and recall
- **THEN** the retrieved identifiers come from the executed graph's retrieval output
- **AND** the expected relevant identifiers are used only as the relevance reference

#### Scenario: Tool metrics use observed tool outcomes

- **WHEN** a tool case computes tool success or failed-claim metrics
- **THEN** the tool outcomes come from the executed graph's bounded tool records
- **AND** expected tool behavior is applied as assertions, not as the observed trace

### Requirement: Complete approval thresholds are applied

The evaluation runner SHALL apply every configured per-case and aggregate approval threshold for text, retrieval, tool, and judge metrics from observed data. Approval SHALL require all configured required thresholds to pass.

#### Scenario: All configured thresholds are enforced

- **WHEN** a case or run completes with observed scores
- **THEN** the runner evaluates every threshold configured for the selected evaluation profile
- **AND** approval fails when any required threshold is not met

#### Scenario: A single missed threshold fails approval

- **WHEN** all thresholds pass except one required retrieval threshold
- **THEN** the case or run is marked failed with that threshold reported

### Requirement: Metric runtime failure is an explicit error

A metric runtime failure SHALL be reported as a metric error and SHALL NOT silently fall back to a differently named metric or to a reference-derived score.

#### Scenario: Metric failure is not a silent fallback

- **WHEN** a required metric cannot be computed at runtime
- **THEN** the case is classified as a metric error
- **AND** no score is recorded under a different metric name as a substitute
