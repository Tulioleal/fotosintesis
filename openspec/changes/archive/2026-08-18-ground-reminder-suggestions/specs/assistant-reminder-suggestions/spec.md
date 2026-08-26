## ADDED Requirements

### Requirement: Evidence-grounded reminder suggestion contract

Reminder suggestions SHALL include the evidence context used to derive them, a confidence indication, limitations, and a concise justification. The justification SHALL persist with the created reminder.

#### Scenario: Suggestion returns evidence context

- **WHEN** the backend returns a reminder suggestion
- **THEN** the suggestion includes the evidence context used to derive it, confidence, limitations, and a concise justification

#### Scenario: Justification persists on acceptance

- **WHEN** the user accepts a suggestion
- **THEN** the created reminder stores the suggestion justification
