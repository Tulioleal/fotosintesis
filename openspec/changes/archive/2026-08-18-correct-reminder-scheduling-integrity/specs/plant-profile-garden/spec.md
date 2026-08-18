## ADDED Requirements

### Requirement: Accurate reminder summaries

The system SHALL derive each garden plant's pending reminder summary from its reminder rows, and the summary SHALL be reconciled by the same counter integrity contract that governs reminders.

#### Scenario: Plant summary reflects pending reminders

- **WHEN** a garden plant's reminder summary is displayed
- **THEN** the pending reminder count matches the plant's pending reminder rows

#### Scenario: Plant summary is reconcilable

- **WHEN** a garden plant's stored active reminder count is out of sync
- **THEN** running reminder counter reconciliation repairs the plant's displayed pending reminder count
