## MODIFIED Requirements

### Requirement: Identification sad paths

The system SHALL handle low confidence, no plant, blurry image, MaaS unavailable and no GBIF match as recoverable states. All user-facing messages for these recoverable states SHALL be in English, and each recoverable state SHALL offer a navigable manual search entry point.

#### Scenario: No reliable candidate

- **WHEN** the image cannot produce a reliable validated candidate
- **THEN** the system explains the issue in English and offers retry, better photo guidance or manual search
- **AND** the manual search option is a navigable control that opens the search experience

#### Scenario: Recoverable state links to search

- **WHEN** the identification flow ends in a low-confidence, no-plant, blurry-image, MaaS-unavailable, or no-GBIF-match recoverable state
- **THEN** the system presents a navigable link or control to manual search alongside retry guidance
