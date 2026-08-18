## ADDED Requirements

### Requirement: Reminder suggestions reuse bounded light context

Reminder suggestions originating from assistant conversations SHALL include light context only when the same owner- and plant-scoped eligibility policy for recommendation use allows it. Suggestion justification SHALL disclose the measurement source, age, and reliability in the same bounded way as care answers, and SHALL NOT include stale, unreliable, or foreign-plant readings.

#### Scenario: Eligible light context appears in suggestion justification

- **WHEN** a reminder suggestion includes light context that passes the shared eligibility policy
- **THEN** the suggestion justification discloses the measurement source, age, and reliability in the same bounded way as care answers

#### Scenario: Ineligible or foreign reading is omitted

- **WHEN** the only available readings are stale, unreliable, or associated with a different plant
- **THEN** the reminder suggestion does not include those readings as light context
