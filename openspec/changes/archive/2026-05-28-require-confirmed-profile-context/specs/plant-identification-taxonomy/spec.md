## MODIFIED Requirements

### Requirement: Confirmation gate

The system MUST block definitive profile generation, garden save and associated reminders until the user confirms a taxonomically validated candidate.

#### Scenario: Unconfirmed candidate action

- **WHEN** a user attempts a definitive action with an unconfirmed or unvalidated candidate
- **THEN** the system blocks the action and asks for confirmation or manual correction

#### Scenario: Profile generation requires confirmed candidate context

- **WHEN** a user attempts to generate or retrieve a definitive plant profile by scientific name without a confirmed validated candidate context
- **THEN** the system blocks profile access and requires the user to confirm a validated candidate first
