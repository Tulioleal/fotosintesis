## Why

The plant profile endpoint can currently generate profiles from a public scientific-name URL without authentication or proof that the requested plant came from a confirmed, validated candidate. This conflicts with the profile requirement that definitive profiles are for confirmed plants and leaves backend behavior weaker than the UI flow.

## What Changes

- Require authenticated user context for plant profile generation/retrieval.
- Require a confirmed, taxonomically validated identification candidate owned by the current user before serving a definitive plant profile.
- Align frontend profile requests with the backend gate by preserving and sending the confirmed candidate context already present in the identify flow.
- Add regression coverage for unauthenticated, unconfirmed, unvalidated, and wrong-user profile access attempts.

## Capabilities

### New Capabilities

- `plant-profile-garden`: Confirmed candidate access requirements for evidence-backed plant profiles.

### Modified Capabilities

- `plant-identification-taxonomy`: Clarify that profile generation is one of the definitive actions protected by the confirmation gate.

## Impact

- Backend API contract for `GET /plant-profiles/{scientific_name}` changes to require authentication and a confirmed candidate identifier.
- Backend profile garden repository or service logic will validate candidate ownership, validation status, confirmation state, and name consistency before creating or returning a profile.
- Frontend profile route/API calls must include the candidate context from the identify flow and handle authorization/conflict failures.
- OpenAPI/client types and tests may need regeneration or updates if the endpoint signature changes.
