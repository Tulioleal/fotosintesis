## MODIFIED Requirements

### Requirement: Evidence-grounded reminder suggestion contract

AI-labeled reminder suggestions SHALL originate from a backend operation that accepts a selected garden plant and an optional user request, resolves the plant's confirmed taxonomy through existing ownership checks, and loads profile evidence, garden location, notes, active reminders, and timezone before proposing a suggestion. Generation SHALL propose a concrete local date, time and recurrence derived from the task type, plant profile cadence, eligible light data, location and current local time, and SHALL justify that derivation in one concise sentence. A schedule field MAY be null only when it is genuinely undeterminable from the delivered context. The timezone SHALL be resolved server-side from the stored user timezone and MUST NOT be requested from the model. The frontend SHALL NOT generate AI-labeled suggestions with local semantic regular expressions or fixed calendar defaults.

#### Scenario: Suggestion originates in the backend

- **WHEN** the reminders page requests a suggestion for a selected garden plant
- **THEN** the backend generates and returns the suggestion

#### Scenario: Proposal includes a justified concrete schedule

- **WHEN** generation completes for an ordinary care task with profile context
- **THEN** the outcome is a suggestion carrying a future local date, time, recurrence and a derivation justification
- **AND** no clarification for date, time or recurrence is emitted

#### Scenario: Clarification is reserved for undeterminable schedules

- **WHEN** the delivered context makes a schedule genuinely undeterminable
- **THEN** the backend returns a clarification naming only the fields it could not determine
- **AND** an unset account timezone is clarified by naming the timezone field
