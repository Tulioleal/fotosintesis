## ADDED Requirements

### Requirement: Authenticated shell applies Fotosíntesis foundation
The authenticated app shell and Home dashboard SHALL apply the archived Fotosíntesis visual foundation as their required design baseline.

#### Scenario: Private shell uses foundation tokens
- **WHEN** private shell styles are authored
- **THEN** they use the shared Fotosíntesis colors, typography, spacing, radius, surface, outline, and elevation tokens instead of introducing unrelated palette, type, or shadow rules

#### Scenario: Home dashboard uses foundation tokens
- **WHEN** the Home dashboard is redesigned
- **THEN** its cards, headings, labels, chips, imagery treatments, empty state, error state, and loading state use the archived Fotosíntesis visual foundation

### Requirement: Authenticated reference copy adaptation
Authenticated shell and Home UI SHALL adapt external reference copy to the Fotosíntesis product voice before exposing it to users.

#### Scenario: Placeholder product names are replaced
- **WHEN** shell or Home UI adapts a reference that contains `PlantCare` or another placeholder product name
- **THEN** visible product copy uses `Fotosíntesis`

#### Scenario: Reference copy does not override product behavior
- **WHEN** the dashboard mosaic reference includes placeholder navigation, feature, or footer copy that does not match the implemented Fotosíntesis routes
- **THEN** the implementation preserves the visual intent while using copy and destinations that match the current authenticated app
