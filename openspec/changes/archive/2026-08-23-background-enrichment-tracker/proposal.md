## Why

Plant identification schedules durable background enrichment after candidate confirmation, but users lose visibility as soon as they leave the profile. The application needs a persistent, cross-page explanation of active work and terminal outcomes so users understand that evidence collection is still running and know where to find the updated profile.

## What Changes

- Add an authenticated, bounded view of the current user's recent and active plant-enrichment jobs.
- Show active enrichment status on Home and Garden surfaces with a link to the relevant profile.
- Preserve status visibility across navigation and reloads without exposing job payloads or private provider details.
- Notify users once when background enrichment reaches a terminal state, including complete, partial, and failed outcomes.
- Distinguish evidence acquisition completion from any subsequent profile snapshot refresh.
- Add accessible loading, terminal, error, and stale-state UI coverage.

## Capabilities

### New Capabilities

- `background-enrichment-tracker`: Cross-page discovery, status, and terminal notifications for authenticated plant-enrichment work.

### Modified Capabilities

- `confirmed-plant-enrichment`: Expose the lifecycle relationship between candidate enrichment and profile refresh to user-facing status consumers.
- `authentication-home`: Include bounded enrichment activity in the authenticated Home experience.
- `plant-profile-garden`: Surface enrichment activity consistently from garden-owned plant views.

## Impact

- Backend job repository, schemas, authenticated APIs, and profile/home/garden response contracts.
- Frontend React Query cache, app shell providers, Home, Garden, profile links, and accessible notification/status components.
- OpenAPI-generated TypeScript contracts and frontend component, API, and end-to-end tests.
- No change to provider selection, evidence validation, taxonomy rules, or enrichment semantics.
