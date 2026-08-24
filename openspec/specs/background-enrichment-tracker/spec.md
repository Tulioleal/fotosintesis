## Purpose

TBD - Created by syncing change `background-enrichment-tracker`.

## Requirements

### Requirement: Owner-scoped enrichment activity

The system SHALL provide an authenticated owner-scoped activity view containing active and bounded recently terminal enrichment jobs associated with that owner. Each item SHALL include only sanitized lifecycle metadata, plant/profile context, bounded result information, limitations, and sanitized failure categories.

#### Scenario: Active enrichment is listed
- **WHEN** an authenticated user has a pending or processing confirmed-plant enrichment job
- **THEN** the activity view includes that work with its lifecycle, plant context, job identifier, and profile navigation context
- **AND** the response excludes raw payloads, source bodies, claims, quotes, prompts, leases, and worker ownership data

#### Scenario: Terminal enrichment remains discoverable
- **WHEN** an owner has a complete, partial, or failed enrichment job inside the configured retention window
- **THEN** the activity view may include its bounded outcome and completion timestamp
- **AND** the item is not returned after the retention window

#### Scenario: Another owner's activity is requested
- **WHEN** a user requests activity for another owner or supplies an unrelated candidate identifier
- **THEN** the response does not reveal that owner's job, candidate, profile, or evidence context

### Requirement: Cross-page background status

The authenticated application SHALL make active background enrichment discoverable from Home and Garden and SHALL link each activity item to its authorized plant profile. The application SHALL stop active polling when no active work remains.

#### Scenario: User navigates away from profile
- **WHEN** enrichment is pending or processing and the user navigates to Home or Garden
- **THEN** the destination displays a concise active-work indicator and a link to the relevant profile
- **AND** the user is told that work continues in the background

#### Scenario: No active work exists
- **WHEN** the activity view contains no pending or processing jobs
- **THEN** Home and Garden do not display an active-work loading indicator
- **AND** the client does not continue active polling solely for enrichment activity

#### Scenario: Activity request fails
- **WHEN** the activity endpoint cannot be refreshed
- **THEN** Home and Garden preserve their primary content
- **AND** display a non-blocking status error with a retry action

### Requirement: Terminal outcome notification

The authenticated frontend SHALL announce a newly observed terminal enrichment outcome at most once per job and outcome version per browser session. Complete, partial, and failed outcomes SHALL have distinct accessible text and SHALL preserve a profile link.

#### Scenario: Enrichment completes
- **WHEN** an observed active job transitions to complete
- **THEN** the application announces that evidence is ready and provides a link to the plant profile

#### Scenario: Enrichment is partial
- **WHEN** an observed active job transitions to partial
- **THEN** the application announces that useful evidence was found with bounded covered and missing counts
- **AND** does not describe the profile as fully complete

#### Scenario: Enrichment fails
- **WHEN** an observed active job transitions to failed
- **THEN** the application announces that evidence expansion failed with sanitized recovery guidance
- **AND** preserves access to the existing plant profile

#### Scenario: Terminal outcome is revisited
- **WHEN** the user reloads or revisits a page after a terminal outcome was already announced in the current session
- **THEN** the activity remains visible when within retention
- **AND** the same outcome is not announced again

### Requirement: Evidence and profile-refresh phase distinction

The activity view SHALL distinguish confirmed-plant evidence enrichment from any subsequent profile-refresh job. User-facing status SHALL NOT claim that profile sections are updated solely because evidence enrichment became terminal.

#### Scenario: Evidence completes before profile refresh
- **WHEN** confirmed-plant enrichment is terminal and a related profile-refresh job is active
- **THEN** the activity view reports evidence as terminal and profile refresh as active
- **AND** the profile link communicates that sections may still be updating

#### Scenario: Both phases complete
- **WHEN** related evidence and profile-refresh jobs are terminal
- **THEN** the activity view may report the profile as updated
- **AND** retains bounded evidence outcome limitations when applicable

### Requirement: Durable refresh causality

The system SHALL associate each surfaced profile-refresh job with its causing enrichment run through a durable many-to-many table recorded transactionally when the refresh is enqueued. Profile-refresh activity SHALL NOT be authorized or discovered through payload species matching. Legacy reconciliation signals SHALL create no association, and historical refresh jobs without an association SHALL remain hidden from activity views.

#### Scenario: Enrichment causes a refresh
- **WHEN** an accepted enrichment run enqueues its profile refresh in the same evidence transaction
- **THEN** one association row links the two jobs and commits or rolls back together with the evidence
- **AND** re-enqueueing the same fingerprint reuses the refresh job without duplicating the association

#### Scenario: Two enrichments share a reused refresh
- **WHEN** a second enrichment run produces the same evidence fingerprint while a refresh is already queued
- **THEN** both enrichment runs are associated with the same refresh job
- **AND** the refresh appears once per owner in activity results

#### Scenario: Unassociated refresh is never exposed
- **WHEN** a refresh job exists without any enrichment association
- **THEN** it is excluded from every owner's activity view

### Requirement: Authorized candidate context for activity links

Every visible activity item SHALL carry an authorized candidate identifier and display name selected deterministically from owner-owned candidates behind the association chain. Candidate ownership SHALL be revalidated at read time using the same predicate as the direct candidate-status query, and the accepted scientific name SHALL take precedence over the payload's normalized binomial for profile navigation.

#### Scenario: Refresh activity carries candidate context
- **WHEN** a causally associated refresh job is visible to an owner
- **THEN** the item exposes the deterministic owner candidate id and the candidate's accepted scientific name
- **AND** every actionable link targets `/profiles/<name>?candidateId=<id>`

#### Scenario: Malformed association cannot bypass ownership
- **WHEN** an association row points a refresh at an enrichment whose candidates the requesting user does not own
- **THEN** the refresh is not returned to that user

### Requirement: Cursor pagination with bounded queries

The activity endpoint SHALL support keyset pagination over the stable `(updated_at DESC, id DESC)` ordering tuple using an opaque cursor, applying the cursor condition inside SQL and returning at most `limit + 1` valid items per phase; when stored-but-unserializable rows would shrink a page, the endpoint MAY fetch additional bounded keyset batches (with a per-phase cap) so valid older rows remain reachable and `has_more` stays accurate. Malformed cursors SHALL fail validation without exposing internals.

#### Scenario: Client walks all pages
- **WHEN** more jobs exist than fit on one page and the client follows `next_cursor` over an unchanged activity dataset
- **THEN** every visible job is returned exactly once across pages
- **AND** tied timestamps are ordered by exact job id descending without duplication or omission
- **AND** items updated during a traversal may move into a subsequent fresh traversal

#### Scenario: Malformed cursor is rejected
- **WHEN** a client supplies a cursor that is not decodable to the ordering tuple
- **THEN** the endpoint responds with HTTP 422 and no stack detail

### Requirement: Mandatory profile context on activity items

Every serialized activity item SHALL include a non-empty scientific name and an authorized candidate identifier; items whose candidate context is missing or blank SHALL be filtered out in SQL rather than returned without a usable link. The frontend SHALL treat both fields as required and render every item's profile navigation from them.

#### Scenario: Item without candidate context is hidden
- **WHEN** a job's only candidate association lacks any display name
- **THEN** that job does not appear in the owner's activity view
- **AND** no item without both fields can pass contract validation

#### Scenario: Accepted name takes precedence
- **WHEN** a candidate's accepted and suggested scientific names differ
- **THEN** the accepted name is used for display and links
- **AND** the refresh payload's normalized binomial never overrides it

### Requirement: Single app-shell activity observer

Exactly one React Query activity observer SHALL exist, owned by a provider mounted once in the authenticated app shell; all consumers read the shared context. Confirmation flows SHALL invalidate the shared activity query after seeding the candidate-detail cache so a stopped tracker wakes immediately, without synthesizing activity items from confirmation responses.

#### Scenario: Confirmation wakes a stopped tracker
- **WHEN** polling has stopped after an empty response and the user confirms a candidate
- **THEN** the invalidation triggers exactly one shared-observer refresh cycle before navigation (that cycle may issue multiple cursor-page requests)
- **AND** a failed confirmation triggers no invalidation

### Requirement: Terminal outcome notification queue

Unseen terminal outcomes SHALL be enqueued newest-first with id tie-breaking, displayed one at a time, advanced on dismissal, and deduplicated by outcome version; only displayed versions SHALL persist to session storage. Every announcement SHALL provide accessible text and a valid profile link, and refresh failures SHALL use refresh-specific recovery guidance distinct from evidence guidance.

#### Scenario: Multiple outcomes arrive together
- **WHEN** complete, partial, and failed outcomes arrive in one response
- **THEN** the newest is announced first and dismissal advances through every queued item
- **AND** identical rerenders of the same response enqueue no duplicates

#### Scenario: Only displayed outcomes persist
- **WHEN** a queued outcome becomes visible
- **THEN** its version is persisted to session storage at display time
- **AND** versions still waiting in the queue remain unannounced on reload

### Requirement: Profile reconciliation after refresh terminal state

The plant profile SHALL consume the shared activity context without creating another observer, keep its candidate-local polling unchanged, and invalidate the exact profile query once per terminal refresh outcome version that is related to the profile's candidate or species. Evidence-phase completion alone SHALL NOT trigger profile-section claims.

#### Scenario: Terminal refresh refreshes profile data once
- **WHEN** a related refresh reaches complete, partial, or failed
- **THEN** the exact profile query (candidate, accepted name, language, per user) is invalidated exactly once for that outcome version
- **AND** repeated identical terminal data does not invalidate again, while a different candidate, language, or user claims independently
