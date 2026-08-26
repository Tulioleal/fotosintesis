## Purpose

Define correctness requirements for automatic evaluation metrics used by offline evaluation runs.
## Requirements
### Requirement: Real BERTScore for referenced text evaluation

The system SHALL compute BERTScore for referenced text outputs using a model-backed BERTScore implementation rather than token-overlap or lexical F1 logic.

#### Scenario: Semantic BERTScore is computed

- **WHEN** a referenced text evaluation has a non-empty reference and non-empty candidate
- **THEN** the system returns BERTScore precision, recall and F1 values produced by the model-backed BERTScore implementation

#### Scenario: Token-overlap fallback is not used

- **WHEN** the BERTScore dependency or model runtime cannot be loaded
- **THEN** the system raises an explicit evaluation error instead of returning token-overlap precision, recall or F1 under the BERTScore metric name

### Requirement: BERTScore output compatibility

The system SHALL preserve the existing BERTScore result shape with `precision`, `recall` and `f1` float values.

#### Scenario: Caller reads BERTScore result

- **WHEN** evaluation code requests BERTScore for a referenced text case
- **THEN** the returned mapping contains `precision`, `recall` and `f1` keys with float values

#### Scenario: Empty text input

- **WHEN** either the reference or candidate text is empty
- **THEN** the system returns `precision`, `recall` and `f1` values of `0.0`

### Requirement: Accurate evaluation report description

The system SHALL describe referenced text metrics accurately in generated evaluation reports.

#### Scenario: Report documents text metrics

- **WHEN** the system renders an evaluation markdown report
- **THEN** the metrics and limitations text identifies BERTScore as a real model-backed metric and does not describe it as token-overlap, dependency-free or merely BERTScore-compatible

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

