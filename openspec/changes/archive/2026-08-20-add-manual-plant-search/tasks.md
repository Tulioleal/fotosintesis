## 1. Data Model Migration

- [x] 1.1 Add Alembic migration `0019_manual_plant_search.py`: make `identification_candidates.identification_id` nullable, add `origin` (default `image_identification`), and add nullable `user_id` FK to `users`.
- [x] 1.2 Update `identification_candidates` in `app/auth/tables.py` to match the migrated columns (nullable `identification_id`, `origin`, nullable `user_id`).
- [x] 1.3 Add a migration integration test covering the new columns and existing-row defaults (no backfill).

## 2. GBIF Candidate Lookup

- [x] 2.1 Add `GbifClient.suggest(query)` (and any shared normalization helper) that returns a bounded list of `GbifTaxonomy` candidates with accepted name, rank, family, genus, and key, reusing existing normalization.
- [x] 2.2 Add unit tests for `suggest`: accepted-species prioritization, rank labeling, and provider failure surfacing as a retryable error.

## 3. Local Search

- [x] 3.1 Add `search_local_profiles(query)` to `PlantProfileGardenRepository` using case-insensitive `ILIKE` over `scientific_name`, `normalized_binomial`, `common_name`, and `aliases`, returning the matched field plus profile identity.
- [x] 3.2 Add unit tests for local matching across scientific, binomial, common, and alias terms, and for empty results.

## 4. Manual Candidate Persistence and Confirmation

- [x] 4.1 Add `create_manual_candidate(...)` and `confirm_manual_candidate(candidate_id, user_id)` to `IdentificationRepository`; validate the structured GBIF identity as `CanonicalSpeciesIdentity` before persisting as `validated` with a fixed `manual` confidence label and null `identification_id`.
- [x] 4.2 Refactor `CandidateConfirmationService` to share the enrichment-scheduling body and add a `confirm_manual()` path; update `confirmed_candidate()` to resolve ownership via `candidate.user_id` or `image.user_id` through an outer join.
- [x] 4.3 Add tests for manual candidate creation (no image, no synthetic confidence), ownership, confirmation reuse, and blocking of unvalidated/unowned candidates.

## 5. Backend Endpoints

- [x] 5.1 Add `app/api/search.py` with `GET /search`, `GET /search/gbif`, `POST /search/candidates`, and `POST /search/candidates/{candidate_id}/confirm`, all behind `get_current_user`, and register it in `app/main.py`.
- [x] 5.2 Add response schemas for local results, GBIF candidates, and the manual candidate/confirmation responses; surface provider errors as retryable without discarding local results.
- [x] 5.3 Update `scripts/check_architecture.py` allowlists only if a new slice-internal import is introduced; otherwise add the new module to the appropriate layering path.

## 6. Frontend Contracts and BFF

- [x] 6.1 Regenerate `openapi.d.ts` via `pnpm openapi:generate` and add the new types/Zod schemas to `generated-contracts.ts`.
- [x] 6.2 Add BFF route handlers for `/api/search`, `/api/search/gbif`, `/api/search/candidates`, and `/api/search/candidates/[candidateId]/confirm` using `resolveBackendAuthHeaders`.
- [x] 6.3 Add `searchPlants`, `searchGbif`, `createManualCandidate`, and `confirmManualCandidate` methods to `apiClient`.

## 7. Search UI and Identification Links

- [x] 7.1 Replace the `/search` `PlaceholderPage` with a functional search experience using TanStack Query, with loading, local-results, external-expansion, empty, and error states, distinguishing local records from external candidates.
- [x] 7.2 Wire candidate selection to create a manual candidate and confirmation to reuse the profile navigation flow.
- [x] 7.3 Add navigable search links from `IdentifyFlow` recoverable states (low-confidence, no-plant, blurry, MaaS-unavailable, no-GBIF-match).
- [x] 7.4 Ensure keyboard navigation, focus management, and asynchronous status announcements (polite live regions) on the search and confirmation screens.

## 8. Tests

- [x] 8.1 Backend: local ranking, GBIF fallback, duplicate collapse by GBIF key/binomial, ownership, and confirmation reuse.
- [x] 8.2 Frontend: React Testing Library coverage for search states and candidate selection; accessibility assertions for keyboard operability.
- [x] 8.3 E2E (Playwright): a manual search journey from search → GBIF candidate → manual candidate → confirm → profile, plus the identification sad-path link to search.
- [x] 8.4 Add a regression test proving search name matching does not introduce keyword-based semantic classification (non-English/synonym terms still route to GBIF/local lookup normally).

## 9. Verification

- [x] 9.1 Run `ruff`, `pytest`, and `scripts/check_architecture.py` in `backend/` and fix failures.
- [x] 9.2 Run `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm openapi:check` in `frontend/` and fix failures.
- [x] 9.3 Run the relevant Playwright E2E suites and confirm the search journey and sad-path links pass.
