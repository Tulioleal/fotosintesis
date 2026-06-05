## ADDED Requirements

### Requirement: Binomial-aware identification presentation
The identification UI SHALL use a concise binomial name for candidate display and assistant navigation when a common name is unavailable, while preserving the full scientific name as secondary taxonomic context.

#### Scenario: Binomial name used as primary candidate text
- **WHEN** an identification candidate has no common name and has a binomial name
- **THEN** the frontend renders the binomial name as the candidate's primary display text

#### Scenario: Scientific name shown only when distinct
- **WHEN** an identification candidate has a full scientific name that differs from the primary display text
- **THEN** the frontend renders the full scientific name as secondary candidate context

#### Scenario: Candidate display falls back without binomial name
- **WHEN** an identification candidate has no common name and no binomial name
- **THEN** the frontend falls back to the accepted scientific name or suggested scientific name for candidate display

#### Scenario: Assistant link includes separated plant context
- **WHEN** the user navigates from an identification candidate to the assistant
- **THEN** the frontend includes separated `plant`, `binomial` and `scientific` query parameters when those values are available
