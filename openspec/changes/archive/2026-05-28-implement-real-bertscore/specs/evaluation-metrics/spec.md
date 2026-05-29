## ADDED Requirements

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
