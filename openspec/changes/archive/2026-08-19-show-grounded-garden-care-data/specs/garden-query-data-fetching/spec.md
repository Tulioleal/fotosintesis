## ADDED Requirements

### Requirement: Provenance-aware garden rendering

The frontend SHALL render garden list and detail care data from the grounded summary fields and SHALL NOT hardcode static care values. Reminder due instants SHALL be rendered in the reminder's effective IANA timezone.

#### Scenario: Card shows next pending action

- **WHEN** a garden card has a next-reminder summary
- **THEN** the card displays the reminder action and its due date in the effective timezone

#### Scenario: Card shows no-care state

- **WHEN** a garden card has no next-reminder summary
- **THEN** the card displays a no-care state and remains a link to the plant detail, which offers a path to create a reminder

#### Scenario: Missing light data renders as missing

- **WHEN** a garden detail has no light summary
- **THEN** the UI renders a missing-data state rather than a static light label

### Requirement: Accessible care states

Confidence, approximation, and error SHALL be communicated with text and SHALL NOT rely on color alone. Loading, empty, error, and partial-data states SHALL remain reachable by keyboard and assistive technology.

#### Scenario: Approximation communicated as text

- **WHEN** a camera-derived light measurement is displayed
- **THEN** the approximation is conveyed through text, not color alone

#### Scenario: Care states remain accessible

- **WHEN** garden care data is missing, partial, or failed
- **THEN** the corresponding state is exposed to assistive technology with textual content
