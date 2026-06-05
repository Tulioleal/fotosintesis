## Why

Identification candidates currently preserve full GBIF-normalized scientific names and taxonomic fields, but do not store a stable binomial name separately. Persisting the binomial name lets downstream features use species-level identity without losing accepted names, infraspecific ranks, or other original taxonomic context.

## What Changes

- Add nullable `binomial_name` metadata to persisted identification candidates.
- Populate `binomial_name` from GBIF `canonicalName` when available.
- Fall back to genus plus species only when both GBIF values are present and reliable.
- Expose `binomial_name` in identification candidate API responses, allowing `null` when no reliable binomial is available.
- Add migration and backend test coverage for persistence, response serialization, null handling, and candidate confirmation.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `plant-identification-taxonomy`: Identification candidates include an optional binomial name alongside full scientific and accepted taxonomic names.

## Impact

- Backend database schema: `identification_candidates.binomial_name` nullable `VARCHAR(240)`.
- Alembic migrations: new migration `0008_identification_candidate_binomial_name.py`.
- SQLAlchemy table definitions, GBIF taxonomy normalization, response schemas, repository persistence, and backend tests.
- No data backfill is required because existing persisted data does not need migration beyond adding the nullable column.
