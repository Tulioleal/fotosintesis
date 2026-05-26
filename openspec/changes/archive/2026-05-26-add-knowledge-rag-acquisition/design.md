## Context

This slice builds the evidence layer before plant profiles and assistant answers depend on it. It should provide services and data structures rather than complete end-user flows.

## Goals / Non-Goals

**Goals:**

- Persist documents, sources, chunks and embeddings with traceable metadata.
- Retrieve by species, topic, source, confidence, review status and date.
- Acquire knowledge from approved trusted sources when evidence is insufficient.
- Re-index newly acquired knowledge and retry retrieval.

**Non-Goals:**

- No final assistant conversation UI.
- No finished plant profile rendering.
- No manual editorial review workflow beyond status fields.

## Decisions

- PostgreSQL + pgvector remains the canonical store for relational and vector data.
- LlamaIndex handles chunking, embedding orchestration and retrieval over pgvector.
- Chunks carry metadata for `species_id`, `scientific_name`, `topic`, `source_domain`, `source_url`, `confidence`, `review_status`, `retrieved_at` and `created_at`.
- Trusted acquisition is restricted to approved domains and must preserve source URLs and dates.

## Risks / Trade-offs

- Auto-ingested knowledge can be wrong; confidence, source traceability and review status are mandatory.
- Web acquisition can add latency; callers need partial-answer and retry paths.
