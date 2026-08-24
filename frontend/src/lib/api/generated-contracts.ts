import { z } from "zod";
import type { components, operations } from "@/lib/generated/openapi";

// ---------------------------------------------------------------------------
// Type-only contracts derived from the OpenAPI operation map.
// These types guarantee that compile-time signature changes are caught
// immediately without touching backend-provided JSON shape details.
// ---------------------------------------------------------------------------

export type ConfirmationResponse =
  operations["confirm_candidate_identifications__identification_id__candidates__candidate_id__confirm_post"]["responses"][200]["content"]["application/json"];

export type CandidateEnrichmentResponse =
  operations["get_candidate_enrichment_identifications_candidates__candidate_id__enrichment_get"]["responses"][200]["content"]["application/json"];

export type EnrichmentActivityResponse =
  operations["get_enrichment_activity_jobs_enrichment_activity_get"]["responses"][200]["content"]["application/json"];

export type SearchLocalResponse =
  operations["search_local_search_get"]["responses"][200]["content"]["application/json"];

export type GbifSearchResponse =
  operations["search_gbif_search_gbif_get"]["responses"][200]["content"]["application/json"];

export type GbifCandidate = components["schemas"]["GbifCandidate"];

export type ManualCandidateCreate = components["schemas"]["ManualCandidateCreate"];

// ---------------------------------------------------------------------------
// Narrow Zod schemas that validate every bounded runtime field.
// ---------------------------------------------------------------------------

export const enrichmentJobResultSchema = z.object({
  outcome: z.enum(["complete", "partial"]),
  policy_version: z.number().int().positive(),
  covered_aspects: z.array(z.string()),
  missing_aspects: z.array(z.string()),
  covered_count: z.number().int().nonnegative(),
  missing_count: z.number().int().nonnegative(),
  limitations: z.array(
    z.enum([
      "missing_required_aspects",
      "safety_evidence_rejected",
      "retry_exhausted",
      "workflow_incomplete",
      "indexing_deferred",
    ])
  ),
  acquisition_avoided: z.boolean(),
});

export const readJobResultSchema = z.object({
  succeeded: z.number().int().nonnegative(),
  skipped: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  partial: z.boolean(),
  limitations: z.array(
    z.enum(["some_claims_failed", "indexing_deferred"])
  ),
});

export const jobStatusSchema = z.enum([
  "pending",
  "processing",
  "complete",
  "partial",
  "failed",
]);

export const jobStatusResponseSchema = z.object({
  id: z.string().uuid(),
  job_type: z.enum([
    "ingest_validated_claims",
    "enrich_confirmed_plant",
  ]),
  status: jobStatusSchema,
  attempt_count: z.number().int().nonnegative(),
  max_attempts: z.number().int().positive(),
  created_at: z.string(),
  updated_at: z.string(),
  completed_at: z.string().nullable().optional(),
  result: z
    .union([enrichmentJobResultSchema, readJobResultSchema, z.null()])
    .optional(),
  last_error: z
    .object({
      category: z.enum([
        "invalid_payload",
        "unsupported_payload_version",
        "unknown_job_type",
        "database_transient",
        "provider_transient",
        "indexing_transient",
        "invariant_violation",
        "attempts_exhausted",
        "unexpected_error",
        "lease_expired",
        "lease_lost",
        "insufficient_evidence",
      ]),
      retryable: z.boolean(),
    })
    .nullable()
    .optional(),
});

export const candidateEnrichmentSchema: z.ZodType<CandidateEnrichmentResponse> =
  z.object({
    candidate_id: z.string().uuid(),
    policy_version: z.number().int().positive(),
    job: jobStatusResponseSchema,
  });

const activityCountSchema = z.number().int().min(0).max(32);

const enrichmentLimitationSchema = z.enum([
  "missing_required_aspects",
  "safety_evidence_rejected",
  "retry_exhausted",
  "workflow_incomplete",
  "indexing_deferred",
]);

export const enrichmentActivityResultSchema = z.object({
  outcome: z.enum(["complete", "partial", "noop"]).nullable().optional(),
  covered_count: activityCountSchema,
  missing_count: activityCountSchema,
  regenerated_section_count: activityCountSchema,
  stale_section_count: activityCountSchema,
  limitations: z.array(enrichmentLimitationSchema).max(10),
});

export const enrichmentActivityItemSchema = z
  .object({
    id: z.string().uuid(),
    job_type: z.enum([
      "ingest_validated_claims",
      "enrich_confirmed_plant",
      "refresh_profile",
    ]),
    phase: z.enum(["evidence", "profile_refresh"]),
    status: jobStatusSchema,
    created_at: z.string().datetime({ offset: true }),
    updated_at: z.string().datetime({ offset: true }),
    completed_at: z.string().datetime({ offset: true }).nullable().optional(),
    species_key: z.string().nullable().optional(),
    scientific_name: z.string().min(1),
    common_name: z.string().nullable().optional(),
    candidate_id: z.string().uuid(),
    result: enrichmentActivityResultSchema.nullable().optional(),
    last_error: z
      .object({
        category: z.enum([
          "invalid_payload",
          "unsupported_payload_version",
          "unknown_job_type",
          "database_transient",
          "provider_transient",
          "indexing_transient",
          "invariant_violation",
          "attempts_exhausted",
          "unexpected_error",
          "lease_expired",
          "lease_lost",
          "insufficient_evidence",
        ]),
        retryable: z.boolean(),
      })
      .nullable()
      .optional(),
  })
  .superRefine((item, context) => {
    const phaseMatches =
      (item.job_type === "enrich_confirmed_plant" &&
        item.phase === "evidence") ||
      (item.job_type === "refresh_profile" &&
        item.phase === "profile_refresh");

    if (!phaseMatches) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Invalid activity phase",
        path: ["phase"],
      });
    }

    // Lifecycle and timestamp consistency mirrors the backend validator.
    const created = Date.parse(item.created_at);
    const updated = Date.parse(item.updated_at);
    if (Number.isFinite(created) && updated < created) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Invalid timestamps",
        path: ["updated_at"],
      });
    }
    const completed = item.completed_at ? Date.parse(item.completed_at) : NaN;
    if (Number.isFinite(created) && Number.isFinite(completed) && completed < created) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Invalid timestamps",
        path: ["completed_at"],
      });
    }
    if (Number.isFinite(completed) && Number.isFinite(updated) && completed > updated) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Invalid timestamps",
        path: ["completed_at"],
      });
    }

    const active = item.status === "pending" || item.status === "processing";
    if (active && item.completed_at) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Active activity cannot carry completed_at",
        path: ["completed_at"],
      });
    }
    if (!active && !item.completed_at) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Terminal activity requires completed_at",
        path: ["completed_at"],
      });
    }

    // Results may only appear on terminal-success rows; contradictory
    // metadata is rejected wholesale.
    const terminalSuccess =
      item.status === "complete" || item.status === "partial";
    if (item.result && !terminalSuccess) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Invalid activity result for status",
        path: ["result"],
      });
    }

    // Mirror the backend's status/outcome map so an incomplete evidence or
    // refresh outcome can never be announced as a contradicting phase.
    const allowedOutcome: Record<string, string[]> = {
      "enrich_confirmed_plant|complete": ["complete"],
      "enrich_confirmed_plant|partial": ["partial"],
      "refresh_profile|complete": ["complete", "noop"],
      "refresh_profile|partial": ["partial"],
    };
    const outcomeKey = `${item.job_type}|${item.status}`;
    if (
      item.result?.outcome &&
      !allowedOutcome[outcomeKey]?.includes(item.result.outcome)
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Result outcome contradicts status/phase",
        path: ["result", "outcome"],
      });
    }
  });

export const enrichmentActivityResponseSchema: z.ZodType<EnrichmentActivityResponse> =
  z.object({
    items: z.array(enrichmentActivityItemSchema).max(100),
    has_more: z.boolean(),
    next_cursor: z.string().max(512).nullable().optional(),
  });

export const taxonomyCandidateSchema = z.object({
  id: z.string().uuid(),
  common_name: z.string().nullable().optional(),
  suggested_scientific_name: z.string(),
  confidence_label: z.string(),
  visible_traits: z.array(z.string()).optional(),
  possible_match_copy: z.string(),
  gbif_key: z.number().int().nullable().optional(),
  gbif_accepted_key: z.number().int().nullable().optional(),
  accepted_scientific_name: z.string().nullable().optional(),
  binomial_name: z.string().nullable().optional(),
  taxonomic_status: z.string().nullable().optional(),
  synonyms: z.array(z.string()).optional(),
  genus: z.string().nullable().optional(),
  family: z.string().nullable().optional(),
  species: z.string().nullable().optional(),
  validation_status: z.enum(["validated", "no_gbif_match"]),
  confirmed_at: z.string().nullable().optional(),
  created_at: z.string().optional(),
});

export const confirmationResponseSchema: z.ZodType<ConfirmationResponse> =
  z.object({
    status: z.string(),
    candidate: taxonomyCandidateSchema,
    enrichment: candidateEnrichmentSchema,
  });

export const localSearchResultSchema = z.object({
  profile_id: z.string().uuid(),
  scientific_name: z.string(),
  common_name: z.string().nullable().optional(),
  binomial_name: z.string().nullable().optional(),
  matched_field: z.enum([
    "scientific_name",
    "binomial_name",
    "common_name",
    "alias",
  ]),
  matched_value: z.string(),
  has_evidence: z.boolean(),
});

export const searchLocalResponseSchema: z.ZodType<SearchLocalResponse> =
  z.object({
    results: z.array(localSearchResultSchema),
  });

export const gbifCandidateSchema: z.ZodType<GbifCandidate> = z.object({
  key: z.number().int().nullable().optional(),
  accepted_key: z.number().int().nullable().optional(),
  accepted_scientific_name: z.string().nullable().optional(),
  binomial_name: z.string().nullable().optional(),
  rank: z.string().nullable().optional(),
  taxonomic_status: z.string().nullable().optional(),
  synonyms: z.array(z.string()).optional(),
  genus: z.string().nullable().optional(),
  family: z.string().nullable().optional(),
  species: z.string().nullable().optional(),
});

export const gbifSearchResponseSchema: z.ZodType<GbifSearchResponse> =
  z.object({
    candidates: z.array(gbifCandidateSchema),
  });

export const manualCandidateCreateSchema: z.ZodType<ManualCandidateCreate> =
  z.object({
    query: z.string().min(1).max(240),
    gbif: gbifCandidateSchema,
  });
