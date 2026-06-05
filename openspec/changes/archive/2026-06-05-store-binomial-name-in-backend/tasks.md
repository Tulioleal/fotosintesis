## 1. Database Schema

- [x] 1.1 Create Alembic migration `backend/migrations/versions/0008_identification_candidate_binomial_name.py` that adds nullable `identification_candidates.binomial_name` as `VARCHAR(240)` on upgrade.
- [x] 1.2 Implement migration downgrade that drops `identification_candidates.binomial_name` without any data backfill logic.
- [x] 1.3 Update `backend/app/auth/tables.py` so `identification_candidates` includes `sa.Column("binomial_name", sa.String(length=240), nullable=True)`.

## 2. Taxonomy Normalization And Persistence

- [x] 2.1 Update `backend/app/identification/gbif.py` taxonomy model to include `binomial_name: str | None = None`.
- [x] 2.2 Populate `binomial_name` from GBIF `canonicalName` when available.
- [x] 2.3 Add fallback construction from GBIF genus plus species only when both values are present; leave `binomial_name` null for incomplete or unreliable data.
- [x] 2.4 Update `backend/app/identification/repository.py` so `add_candidate()` persists `binomial_name=taxonomy.binomial_name`.

## 3. API Schema

- [x] 3.1 Update `backend/app/identification/schemas.py` so `TaxonomyCandidate` exposes `binomial_name: str | None = None`.
- [x] 3.2 Verify response construction includes `binomial_name` from persisted candidate rows without dropping existing scientific, accepted, genus, family, or species fields.

## 4. Tests

- [x] 4.1 Update `backend/tests/test_auth_home.py` so `POST /identifications` returns `binomial_name` for a GBIF response with canonical name.
- [x] 4.2 Add test coverage that the candidate row is persisted with `binomial_name`.
- [x] 4.3 Verify candidate confirmation still works after adding the new nullable field.
- [x] 4.4 Add test coverage that responses allow `binomial_name: null` when GBIF does not provide a reliable canonical/binomial name.
- [x] 4.5 Run the relevant backend test suite and fix any regressions.
