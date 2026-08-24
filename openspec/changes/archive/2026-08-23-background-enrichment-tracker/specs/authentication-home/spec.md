## MODIFIED Requirements

### Requirement: Home mobile-first

The system SHALL show an authenticated Home dashboard with access to identification, search, light meter, reminders, My Garden and assistant. The Home presentation SHALL follow the Fotosíntesis dashboard mosaic reference while preserving the `GET /home/summary` API flow and the English `HomeAccessItem.label` backend contract. When the authenticated user has active or recently terminal enrichment activity, Home SHALL also expose a bounded background-work indicator without blocking primary dashboard actions.

#### Scenario: Home opens for authenticated user
- **WHEN** a user opens Home with a valid session
- **THEN** the system fetches `GET /home/summary`
- **AND** shows a Fotosíntesis dashboard with a welcome section, primary identification CTA, quick-access mosaic, secondary feature access, and bottom navigation with the active Home section

#### Scenario: Home shows active enrichment
- **WHEN** the authenticated user has pending or processing enrichment activity
- **THEN** Home displays a concise background-work status with the plant context and an authorized profile link
- **AND** the dashboard remains usable while the activity status refreshes

#### Scenario: Home shows terminal enrichment
- **WHEN** the authenticated user has a recently terminal complete, partial, or failed enrichment activity
- **THEN** Home may display its sanitized outcome and profile link within the configured retention window
- **AND** does not expose raw evidence or provider details

#### Scenario: Home summary contract
- **WHEN** Home data loads successfully
- **THEN** the response continues to provide the existing garden summary and access entries
- **AND** the `HomeAccessItem.label` values for these access entries are in English: `My Garden`, `Identify plant`, `Search plants`, `Light meter`, `Reminders`, `Assistant`
