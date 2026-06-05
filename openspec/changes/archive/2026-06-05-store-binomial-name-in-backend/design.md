## Context

Plant identification candidates are normalized through GBIF before being persisted and returned by the backend. The existing model stores full scientific and accepted names plus taxonomic metadata such as genus, family, and species, but does not separately store the species-level binomial name when the GBIF result represents an infraspecific, uncertain, or otherwise more specific taxon.

The change is limited to backend persistence and serialization. There is no existing production data to backfill, so the migration can add a nullable column without data transformation.

## Goals / Non-Goals

**Goals:**

- Persist an optional `binomial_name` for each identification candidate.
- Prefer GBIF `canonicalName` as the source for the binomial/canonical value.
- Preserve existing full scientific, accepted, and taxonomic fields without truncating or replacing them.
- Return `binomial_name` in identification candidate responses, including `null` when no reliable value is available.
- Cover persistence, response serialization, null behavior, and candidate confirmation in backend tests.

**Non-Goals:**

- Backfill historical candidate rows.
- Infer binomials from arbitrary scientific-name string parsing.
- Change frontend presentation or selection behavior.
- Change GBIF matching strategy beyond exposing the normalized binomial value.

## Decisions

- Store `binomial_name` as nullable `VARCHAR(240)` on `identification_candidates`.
  Alternative considered: derive it at response time from existing fields. Persisting it keeps the normalized GBIF value stable with the candidate and avoids reapplying derivation rules later.

- Populate from GBIF `canonicalName` first.
  Alternative considered: use the first two words of the scientific name. That risks dropping or misrepresenting hybrid, uncertain, cultivar, or infraspecific taxa and should not be the primary rule.

- Fall back only from GBIF genus plus species when both are present.
  Alternative considered: broader heuristics using partial taxonomy. Keeping the fallback narrow avoids creating misleading binomial values for genus-only or incomplete identifications.

- Leave `binomial_name` nullable through the database, domain model, and response schema.
  Alternative considered: require an empty string for missing values. `null` better communicates that no reliable value was available.

## Risks / Trade-offs

- GBIF `canonicalName` can include rank-specific canonical text for infraspecific taxa rather than only two words -> Backend tests should document the expected value for representative GBIF fixtures, and implementation should only use genus plus species fallback when canonical data is absent.
- Some candidates will return `binomial_name: null` -> API consumers must treat the field as optional and continue relying on existing scientific-name fields for full context.
- The new response field may require generated clients to refresh types later -> This change only updates backend artifacts; client regeneration can be handled by implementation if the project workflow requires it.

## Migration Plan

- Add Alembic migration `0008_identification_candidate_binomial_name.py` with `upgrade` adding the nullable column and `downgrade` dropping it.
- Update SQLAlchemy metadata to include the new nullable string column.
- Deploy without backfill; existing or newly created rows may contain `null`.
- Rollback by running the downgrade, which drops only the new nullable column.

## Open Questions

- None.
