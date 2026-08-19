## ADDED Requirements

### Requirement: Efficient next pending reminder selection

The system SHALL select each garden plant's earliest pending reminder without issuing one reminder request per garden plant. Completed and cancelled reminders SHALL be excluded from next-reminder selection.

#### Scenario: Next reminder reflects earliest pending row

- **WHEN** a garden plant has multiple pending reminders
- **THEN** the selected next reminder is the one with the earliest due instant

#### Scenario: Completed and cancelled reminders excluded

- **WHEN** a garden plant has only completed or cancelled reminders
- **THEN** no next-reminder summary is returned for that plant

#### Scenario: Single batched selection for garden list

- **WHEN** a garden list is retrieved for many plants
- **THEN** next-reminder summaries are resolved with a batched selection rather than one query per plant
