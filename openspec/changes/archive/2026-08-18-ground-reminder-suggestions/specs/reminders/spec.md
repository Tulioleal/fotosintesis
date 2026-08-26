## ADDED Requirements

### Requirement: Backend-generated reminder suggestions

AI-labeled reminder suggestions SHALL originate from a backend operation that accepts a selected garden plant and an optional user request, resolves the plant's confirmed taxonomy through existing ownership checks, and loads profile evidence, garden location, notes, active reminders, and timezone before proposing a suggestion. The frontend SHALL NOT generate AI-labeled suggestions with local semantic regular expressions or fixed calendar defaults.

#### Scenario: Suggestion originates in the backend

- **WHEN** the reminders page requests a suggestion for a selected garden plant
- **THEN** the backend generates and returns the suggestion
- **AND** the frontend does not derive the action with local semantic regexes or fixed calendar defaults

#### Scenario: Suggestion resolves confirmed taxonomy

- **WHEN** the backend generates a suggestion for a selected garden plant
- **THEN** it resolves the plant's confirmed taxonomy through the existing ownership checks
- **AND** it does not treat nickname or display name as evidence taxonomy

### Requirement: Reminder suggestion duplicate detection

The system SHALL detect equivalent active reminders before returning a suggestion and SHALL recheck duplicates during creation. Equivalence considers the garden plant, the schema-validated action intent, and schedule overlap.

#### Scenario: Equivalent reminder already pending

- **WHEN** an equivalent pending reminder already exists for the same garden plant and schedule
- **THEN** the backend returns a reference to the existing reminder instead of a duplicate draft

#### Scenario: Duplicate rechecked at creation

- **WHEN** a suggestion is accepted and creation runs
- **THEN** the creation endpoint rechecks for duplicates transactionally to avoid races
