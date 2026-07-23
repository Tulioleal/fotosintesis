import { z } from "zod";
import type { operations } from "@/lib/generated/openapi";

// ---------------------------------------------------------------------------
// Type-only contracts derived from the OpenAPI operation map.
// These types guarantee that compile-time signature changes are caught
// immediately without touching backend-provided JSON shape details.
// ---------------------------------------------------------------------------

export type ConfirmationResponse =
  operations["confirm_candidate_identifications__identification_id__candidates__candidate_id__confirm_post"]["responses"][200]["content"]["application/json"];

export type CandidateEnrichmentResponse =
  operations["get_candidate_enrichment_identifications_candidates__candidate_id__enrichment_get"]["responses"][200]["content"]["application/json"];

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
    z.enum(["missing_required_aspects", "safety_evidence_rejected"])
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
    job_type: z.enum(["ingest_validated_claims", "enrich_confirmed_plant"]),
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

export const confirmationResponseSchema: z.ZodType<ConfirmationResponse> =
  z.object({
    status: z.string(),
    candidate: z.object({
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
    }),
    enrichment: candidateEnrichmentSchema,
  });
