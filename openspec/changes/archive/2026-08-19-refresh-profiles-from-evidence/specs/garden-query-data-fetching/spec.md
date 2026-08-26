## ADDED Requirements

### Requirement: Profile cache refresh after section replacement

The frontend SHALL invalidate and refresh cached profile data after a committed profile section replacement so profile queries reflect the new active version without blocking profile reads during regeneration.

#### Scenario: Committed replacement refreshes profile queries

- **WHEN** a profile section replacement commits
- **THEN** affected profile queries are invalidated and refreshed through TanStack Query

#### Scenario: In-progress refresh does not block reads

- **WHEN** a profile section is refreshing in the background
- **THEN** existing profile reads remain available and the UI communicates refresh state without blocking navigation
