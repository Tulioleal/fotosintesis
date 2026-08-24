-- Reproduce the activity query plans recorded in
-- docs/background-enrichment-tracker.md (Query Plan Review).
--
-- Run with:
--   psql "$DATABASE_URL" -v user_id=<uuid> -v limit=21 -f scripts/db/activity_query_plan.sql

-- Bind a default owner so the ownership predicates below are anchored to a
-- concrete value and the script is runnable without failing on an unset
-- variable. Override on the command line to profile a real owner.
\set user_id '''00000000-0000-0000-0000-000000000000''::uuid'
\set limit 21

\echo '=== Evidence phase: candidate-association page ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM (
    SELECT
        j.id,
        j.updated_at,
        ic.id AS ctx_candidate_id,
        COALESCE(ic.accepted_scientific_name, ic.suggested_scientific_name) AS ctx_scientific_name,
        ic.common_name AS ctx_common_name,
        row_number() OVER (
            PARTITION BY j.id
            ORDER BY cej.created_at DESC, ic.id DESC
        ) AS candidate_rank
    FROM application_jobs j
    JOIN candidate_enrichment_jobs cej ON cej.job_id = j.id
    JOIN identification_candidates ic ON ic.id = cej.candidate_id
    LEFT JOIN identification_images ii ON ii.id = ic.identification_id
    WHERE cej.user_id = :user_id
      AND j.job_type = 'enrich_confirmed_plant'
      AND (
          j.status IN ('pending', 'processing')
          OR j.completed_at >= now() - interval '24 hours'
      )
      AND (
          ic.user_id = :user_id
          OR ii.user_id = :user_id
      )
      AND ic.id IS NOT NULL
      AND COALESCE(ic.accepted_scientific_name, ic.suggested_scientific_name) IS NOT NULL
      AND length(trim(COALESCE(ic.accepted_scientific_name, ic.suggested_scientific_name))) > 0
) ranked
WHERE ranked.candidate_rank = 1
ORDER BY ranked.updated_at DESC, ranked.id DESC
LIMIT :limit;

\echo '=== Refresh phase: causal-association page ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM (
    SELECT
        rj.id,
        rj.updated_at,
        ic.id AS ctx_candidate_id,
        COALESCE(ic.accepted_scientific_name, ic.suggested_scientific_name) AS ctx_scientific_name,
        ic.common_name AS ctx_common_name,
        row_number() OVER (
            PARTITION BY rj.id
            ORDER BY cej.created_at DESC, ic.id DESC
        ) AS candidate_rank
    FROM application_jobs rj
    JOIN profile_refresh_enrichment_jobs prej
         ON prej.refresh_job_id = rj.id
    JOIN application_jobs cj ON cj.id = prej.enrichment_job_id
    JOIN candidate_enrichment_jobs cej ON cej.job_id = prej.enrichment_job_id
    JOIN identification_candidates ic ON ic.id = cej.candidate_id
    LEFT JOIN identification_images ii ON ii.id = ic.identification_id
    WHERE rj.job_type = 'refresh_profile'
      AND cj.job_type = 'enrich_confirmed_plant'
      AND cej.user_id = :user_id
      AND (
          rj.status IN ('pending', 'processing')
          OR rj.completed_at >= now() - interval '24 hours'
      )
      AND (
          ic.user_id = :user_id
          OR ii.user_id = :user_id
      )
      AND ic.id IS NOT NULL
      AND COALESCE(ic.accepted_scientific_name, ic.suggested_scientific_name) IS NOT NULL
      AND length(trim(COALESCE(ic.accepted_scientific_name, ic.suggested_scientific_name))) > 0
) ranked
WHERE ranked.candidate_rank = 1
ORDER BY ranked.updated_at DESC, ranked.id DESC
LIMIT :limit;
