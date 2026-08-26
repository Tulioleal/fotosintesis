## Purpose

Define how Mi Jardin frontend data fetching uses TanStack Query for garden reads, writes and user-visible query states.

## Requirements

### Requirement: Garden reads use TanStack Query
The frontend SHALL load garden list and garden detail data through TanStack Query rather than component-local effect-driven fetch state.

#### Scenario: Garden list loads through a query
- **WHEN** an authenticated user opens Mi Jardin
- **THEN** the garden list request is executed through a TanStack Query query function using the frontend API client boundary

#### Scenario: Garden search uses query input
- **WHEN** an authenticated user submits a garden search
- **THEN** the garden list query uses the submitted search text as part of its query input and renders matching results from the response

#### Scenario: Garden detail loads through a query
- **WHEN** an authenticated user opens a saved plant detail page
- **THEN** the garden detail request is executed through a TanStack Query query function keyed by the garden id

### Requirement: Garden query states are user visible
The frontend SHALL render accessible user-facing loading, error, empty, and success states for garden query results.

#### Scenario: Garden list query is loading
- **WHEN** the garden list query is pending
- **THEN** the UI shows the existing garden loading message or an equivalent accessible loading state

#### Scenario: Garden list query fails
- **WHEN** the garden list query fails
- **THEN** the UI shows a user-facing error message and does not render stale results as if they were current

#### Scenario: Garden list query returns no plants
- **WHEN** the garden list query succeeds with an empty list
- **THEN** the UI shows the existing empty garden guidance with a path to identify a plant

#### Scenario: Garden detail query fails
- **WHEN** the garden detail query fails
- **THEN** the UI shows a user-facing error message instead of the detail content

### Requirement: Garden writes use TanStack Query mutations
The frontend SHALL save and delete garden plants through TanStack Query mutations and reconcile related garden query cache entries after successful writes.

#### Scenario: Plant save succeeds
- **WHEN** an authenticated user saves a confirmed plant from a plant profile
- **THEN** the save operation runs as a mutation and invalidates garden list queries after success

#### Scenario: Plant save fails
- **WHEN** a garden save mutation fails
- **THEN** the UI shows a user-facing save error and allows the user to attempt the save again

#### Scenario: Plant delete succeeds
- **WHEN** an authenticated user deletes a saved garden plant
- **THEN** the delete operation runs as a mutation and invalidates affected garden list and detail queries after success
#### Scenario: Plant delete requires reminder confirmation

- **WHEN** the delete mutation receives a reminder-confirmation conflict
- **THEN** the UI preserves the confirmation prompt behavior before retrying the delete with confirmation

### Requirement: Profile cache refresh after section replacement

The frontend SHALL invalidate and refresh cached profile data after a committed profile section replacement so profile queries reflect the new active version without blocking profile reads during regeneration.

#### Scenario: Committed replacement refreshes profile queries

- **WHEN** a profile section replacement commits
- **THEN** affected profile queries are invalidated and refreshed through TanStack Query

#### Scenario: In-progress refresh does not block reads

- **WHEN** a profile section is refreshing in the background
- **THEN** existing profile reads remain available and the UI communicates refresh state without blocking navigation

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
