## Why

The authenticated `/search` route is still a placeholder, and the identification recoverable states (low confidence, no plant, no GBIF match, provider failure) point users at "manual search" without a real destination. Users have no way to find a plant by common, alias, or scientific name and carry it through the existing confirmation and profile workflow when an uploaded image did not produce a reliable match.

## What Changes

- Replace the protected `/search` placeholder with a functional search experience.
- Add an authenticated backend plant search endpoint that searches local profiles by accepted scientific name, binomial name, common name, and aliases.
- Add a controlled GBIF candidate lookup, exposed only on explicit expansion or when local results are absent, and only ever as unconfirmed taxonomic candidates.
- Let a user create a manual candidate from a selected GBIF identity without uploading an image, stored as an unconfirmed candidate owned by the user.
- Reuse the existing confirmation gate, enrichment scheduling, and profile/garden flows for confirmed manual candidates.
- Link the identification recoverable states to the search route.

## Capabilities

### New Capabilities

- `manual-plant-search`: Local and controlled external plant discovery by name, producing user-owned unconfirmed manual candidates that reuse the existing confirmation and profile workflow.

### Modified Capabilities

- `plant-identification-taxonomy`: Support validated candidates that originate from manual search rather than an image, and make identification recoverable states navigate to search.
- `authentication-home`: Replace the search placeholder with a real protected flow.

## Impact

- Backend: new search endpoint and manual-candidate schemas/repository methods; a `GbifClient` name-lookup method; a migration adding candidate origin/ownership metadata and allowing candidates without an image.
- Frontend: a `/search` BFF route, generated OpenAPI contracts, TanStack Query search state, and search components; links from `IdentifyFlow` recoverable states.
- Reuses `plant-profile-garden` confirmation/profile behavior unchanged (no spec change there).
- Tests: local ranking, GBIF fallback, manual candidate ownership, confirmation reuse, sad-path links, and accessibility.
