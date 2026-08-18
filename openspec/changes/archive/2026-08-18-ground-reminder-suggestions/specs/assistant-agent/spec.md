## ADDED Requirements

### Requirement: Structured reminder suggestion generation

The assistant SHALL generate reminder suggestions as schema-validated structured output grounded in contextual evidence: confirmed taxonomy, profile evidence, garden location, notes, active reminders, and timezone. It SHALL load a valid light measurement only when semantic classification requires it, and SHALL NOT derive action intent from semantic regular expressions or fixed calendar defaults.

#### Scenario: Suggestion grounded in evidence

- **WHEN** the assistant generates a reminder suggestion
- **THEN** it produces schema-validated structured output using confirmed taxonomy, profile evidence, garden location, notes, active reminders, and timezone

#### Scenario: Light loaded only when relevant

- **WHEN** semantic classification does not require light context
- **THEN** the assistant does not load a light measurement for the suggestion

#### Scenario: No regex or fixed defaults

- **WHEN** the assistant generates a suggestion
- **THEN** action intent and schedule come from schema-validated model output, not from semantic regular expressions or fixed next-day defaults
