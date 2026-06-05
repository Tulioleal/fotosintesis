## Context

The identification frontend currently treats the full accepted or suggested scientific name as the main display and navigation value. That value can be verbose because it may include authority, variety, subspecies or other taxonomic qualifiers. The backend identification response is planned to expose `binomial_name`, and the frontend should use that concise canonical value for display fallback and assistant handoff without losing full scientific-name context.

The assistant chat currently accepts a single `plant` string from the frontend. That field remains useful for display and backwards compatibility, but plant-care search, structured lookup and RAG acquisition benefit from receiving a concise binomial name separately from the full scientific name.

## Goals / Non-Goals

**Goals:**

- Make identification candidate rendering prefer `common_name`, then `binomial_name`, then existing scientific-name fallbacks.
- Keep the full scientific name available as secondary context when it differs from the primary display name.
- Pass separated `plant`, `binomial` and `scientific` context through assistant navigation.
- Send `plant_binomial_name` and `plant_scientific_name` in assistant chat requests when available.
- Preserve compatibility with existing identification responses and chat URLs that only provide `plant`.
- Cover the behavior with frontend component tests.

**Non-Goals:**

- Add or migrate backend persistence for `binomial_name`.
- Backfill existing data.
- Change profile or garden data models unless needed by the assistant link behavior.
- Replace generated OpenAPI typing across the frontend.

## Decisions

- Use a local display fallback chain in `IdentifyFlow.tsx`: `common_name`, `binomial_name`, `accepted_scientific_name`, `suggested_scientific_name`. This keeps the UI concise while preserving existing behavior when the new field is absent. Alternative considered: always display `binomial_name`; this would hide useful common names and degrade user readability.
- Show the full scientific name only as secondary text when it differs from the primary display value. This avoids duplicate lines such as `Solanum lycopersicum` repeated twice while still surfacing taxonomic detail for verbose names. Alternative considered: remove scientific-name display entirely; this would reduce transparency for identification confidence and taxonomy validation.
- Keep `plant` in assistant requests and add optional `plant_binomial_name` and `plant_scientific_name`. This avoids a breaking API change and lets older `plant`-only links continue working. Alternative considered: replace `plant` with a nested `plant_context` object; that is cleaner but requires broader backend and frontend contract changes.
- Use query parameters `plant`, `binomial` and `scientific` for assistant navigation. This keeps links shareable and easy to construct from identification results. Alternative considered: persist selected candidate context in client state; that would break direct navigation and refresh behavior.

## Risks / Trade-offs

- Backend may not yet return `binomial_name` for candidates -> The UI must tolerate missing `binomial_name` and fall back to existing scientific fields.
- Query strings can become long for verbose scientific names -> Use encoded query parameters and keep the display `plant` value concise where possible.
- Assistant backend may initially ignore the new optional fields -> Preserve the existing `plant` field so chat remains functional until backend handling is implemented.
- Local frontend candidate types can drift from OpenAPI types -> Add test coverage and keep `binomial_name` nullable to match the backend response contract.

## Migration Plan

Deploy as a frontend-compatible change with optional request fields. Existing links and payloads that only contain `plant` continue to work. Rollback is a standard frontend/backend code rollback because no data migration is included.

## Open Questions

- Should profile and garden assistant links also include `binomial` once profile data exposes `binomial_name`?
- Should the assistant UI show both display and binomial context, or only the concise display value with binomial as hidden request context?
