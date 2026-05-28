## Purpose

Define required regression coverage for reminder behavior across the frontend manager component, backend API routes, and repository persistence layer.

## Requirements

### Requirement: Reminder manager component coverage
The frontend test suite SHALL include focused tests for `RemindersManager` user-visible states and mutations.

#### Scenario: Loading and empty garden states
- **WHEN** garden or reminder data is loading, or the garden has no plants
- **THEN** the component tests verify the corresponding loading or empty-state messages and disabled reminder creation behavior

#### Scenario: Form validation prevents invalid submission
- **WHEN** a user submits missing required fields or a non-future date and time
- **THEN** the component tests verify validation messages are shown and no create or update API call is made

#### Scenario: Creating a reminder
- **WHEN** a user fills valid reminder fields and submits the form
- **THEN** the component tests verify the create API receives the expected payload, reminder and garden queries are invalidated, and the success notice is shown

#### Scenario: Editing an existing reminder
- **WHEN** a user selects a pending reminder for editing, changes fields, and submits
- **THEN** the component tests verify the update API receives the reminder id and expected payload, and the form returns to create mode after success

#### Scenario: Completing and deleting reminders
- **WHEN** a user completes or deletes a reminder
- **THEN** the component tests verify the corresponding API call is made and the expected completion or deletion notice is shown

#### Scenario: Accepting a suggestion
- **WHEN** a user accepts a generated reminder suggestion
- **THEN** the component tests verify the create API receives the suggested reminder payload including suggestion justification

#### Scenario: Mutation and query failures
- **WHEN** reminder loading or mutation calls fail
- **THEN** the component tests verify the relevant error or notice is rendered without crashing the component

### Requirement: Reminder API route coverage
The backend test suite SHALL include route-level tests for `backend/app/api/reminders.py` reminder endpoints.

#### Scenario: Authenticated reminder CRUD flow
- **WHEN** an authenticated user creates, lists, updates, completes, and deletes a reminder through HTTP endpoints
- **THEN** the route tests verify expected status codes, response bodies, and ownership-scoped results

#### Scenario: Route validation and not-found responses
- **WHEN** a reminder request uses a past due date, a plant outside the user's garden, or an unknown reminder id
- **THEN** the route tests verify the current 422 or 404 responses and error details

#### Scenario: Unauthenticated access is rejected
- **WHEN** reminder endpoints are called without authentication
- **THEN** the route tests verify the request is rejected with the existing authentication failure response

### Requirement: Reminder repository coverage
The backend test suite SHALL include repository-level tests for `backend/app/reminders/repository.py` persistence behavior.

#### Scenario: Create and list reminders
- **WHEN** a reminder is created for a plant owned by the user
- **THEN** the repository tests verify the reminder is persisted, returned with plant display data, list ordering is stable, and the plant active reminder count increments

#### Scenario: Garden ownership is enforced
- **WHEN** create or update references a garden plant not owned by the user
- **THEN** the repository tests verify no reminder is created or moved and `None` is returned

#### Scenario: Update persists partial fields
- **WHEN** selected reminder fields are updated
- **THEN** the repository tests verify only supplied fields change and omitted fields are preserved

#### Scenario: Delete adjusts active counts
- **WHEN** a pending reminder is deleted
- **THEN** the repository tests verify deletion succeeds and the plant active reminder count decrements

#### Scenario: Completion handles recurrence
- **WHEN** a pending recurring reminder is completed
- **THEN** the repository tests verify the original reminder is completed, a next occurrence is created, and the returned reminder exposes `next_occurrence_at`

#### Scenario: Missing and already completed reminders are stable
- **WHEN** repository operations target missing reminders or complete an already completed reminder
- **THEN** the repository tests verify the methods return the existing `None`, `False`, or unchanged reminder behavior without changing counts unexpectedly
