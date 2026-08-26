## Context

`/search` is still a `PlaceholderPage`, and the identification recoverable states tell users to "use manual search" without a real destination. The candidate model is tightly coupled to images: `identification_candidates.identification_id` is a non-null FK to `identification_images`, and confirmation (`CandidateConfirmationService.confirm`) and profile access (`confirmed_candidate`) resolve ownership through that image row. There is no name-based lookup — `GbifClient` only exposes single-name `match_name`.

The goal is a manual path that reuses as much of the existing confirmation, enrichment, and profile machinery as possible, without a parallel candidate model or a parallel confirmation flow.

## Goals / Non-Goals

**Goals:**

- Search local profiles by scientific, binomial, common, and alias names with database-backed textual matching.
- Offer a controlled GBIF lookup that returns normalized, unconfirmed candidates.
- Create a user-owned, unconfirmed manual candidate from a selected GBIF identity, without an image or synthetic confidence.
- Route confirmed manual candidates through the existing enrichment scheduling and profile/garden flows with identical ownership and validation requirements.
- Link identification recoverable states to search and make the search experience keyboard-accessible.

**Non-Goals:**

- No Trefle or Perenual search. GBIF is the only external provider.
- No image identification from the search route.
- No automatic garden save on selection; a manual candidate stays unconfirmed until the user confirms it.
- No acceptance of arbitrary unvalidated free-form taxonomy; only structured, GBIF-normalized identities are persisted.
- No change to `plant-profile-garden` requirements — the profile/garden gate already keys on "a confirmed, validated candidate that belongs to the user", which a manual candidate satisfies.

## Decisions

### Reuse `identification_candidates` with origin metadata instead of a new table

A separate `manual_search_candidates` table would duplicate ~15 taxonomy columns and force the profile/garden and enrichment code to accept two candidate types. Instead, add three small columns to the existing table:

- `origin` (`image_identification` | `manual_search`, default `image_identification`)
- `user_id` (nullable FK; set for manual candidates, null for image candidates so existing image ownership is untouched)
- `identification_id` becomes nullable (null for manual candidates)

This keeps a single confirmed-candidate concept. `confirmed_candidate()` resolves ownership with `or_(candidate.user_id == user_id, image.user_id == user_id)` via an outer join, so both origins flow through the unchanged profile/garden gate.

### Extract the enrichment scheduling and add a manual confirmation path

`CandidateConfirmationService.confirm()` currently requires an `identification_id`. Refactor it so the enrichment-scheduling body (snapshot creation, `associate_candidate_enrichment`, response assembly) is shared, with two thin entry points:

- `confirm()` — the existing image path, keeping the image ownership/status check.
- `confirm_manual()` — resolves the candidate by `user_id` and `validation_status`, sets `confirmed_at`, then runs the same scheduling.

`IdentificationRepository` gains `confirm_manual_candidate(candidate_id, user_id)` and `create_manual_candidate(...)`. This avoids duplicating the ~90 lines of snapshot/enrichment logic.

### Local search reads `plant_profiles` only

`plant_profiles` already stores `scientific_name`, `normalized_binomial`, `common_name`, and `aliases` (JSON). Local search is a single repository method (`search_local_profiles(query)`) doing case-insensitive `ILIKE` over those fields, returning the matched field and the profile identity. Taxonomy provenance snapshots are not a search surface (no common names/aliases), so they are excluded to avoid scope creep. Textual name lookup is deterministic but non-semantic — it does not classify botanical meaning and does not use keyword lists.

### One new GBIF list method on the existing client

Add `GbifClient.suggest(query)` using GBIF's name-suggest/name-search endpoint, reusing the existing `GbifTaxonomy` normalization (accepted name, rank, family, genus, key, binomial). GBIF remains the single external provider; a provider failure returns a retryable error and never discards local results.

### Manual candidate confidence is a fixed neutral label

Manual candidates store a constant `confidence_label` (`manual`) and no confidence score. The existing `TaxonomyCandidate` schema already treats `confidence_label` as a plain string, so the image UI's confidence copy simply never renders a synthetic value for manual candidates. No new confidence enum or scoring path is introduced.

### Reuse generated contracts and TanStack Query on the frontend

Backend additions flow through the existing OpenAPI export/generate step into `openapi.d.ts` and `generated-contracts.ts`. The search page uses TanStack Query for loading/error/retry state, mirroring the existing garden/identify patterns. New BFF routes (`/api/search`, `/api/search/gbif`, `/api/search/candidates`, `/api/search/candidates/[candidateId]/confirm`) proxy with the existing `resolveBackendAuthHeaders`.

## Risks / Trade-offs

- [Common names are ambiguous] → Every candidate, local or external, stays unconfirmed until the user reviews taxonomy and confirms; external candidates are explicitly labeled.
- [GBIF returns many ranks] → Label rank and prioritize accepted species-level candidates in the suggest response.
- [Local and external duplicates] → Collapse by GBIF accepted key, with binomial fallback, so the same plant is not shown twice.
- [Client-tampered manual-candidate identity] → The create endpoint accepts only a structured GBIF identity and validates it as a `CanonicalSpeciesIdentity` before persisting as `validated`; it never accepts free text.
- [Nullable `identification_id` touches several queries] → Limit the change to `confirm_candidate`/`confirmed_candidate`/insert sites; keep image ownership paths unchanged, and cover both origins in tests.

## Migration Plan

Add one Alembic migration that (1) makes `identification_candidates.identification_id` nullable, (2) adds `origin` with a server default of `image_identification`, and (3) adds a nullable `user_id` FK. Existing rows keep `origin=image_identification` and null `user_id`, so no backfill is required. Rollback redeploys the previous backend image; the new nullable columns are additive for existing rows and the previous code does not read them.

## Open Questions

- Should the GBIF suggest endpoint page/limit results, and what page size balances latency against candidate coverage?
- Is a single fixed `manual` confidence label sufficient for all manual-candidate UI, or should the search results screen use distinct copy instead of the confidence chip?
