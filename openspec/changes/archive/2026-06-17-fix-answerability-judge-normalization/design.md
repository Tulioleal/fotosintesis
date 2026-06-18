## Context

Plant-care answers rely on an answerability judge to decide whether local RAG evidence, structured evidence, or combined RAG plus web evidence directly covers the requested `required_aspects`. The assistant then uses the normalized answerability result for diagnostics, fallback routing, final answer synthesis, source attribution, and validated web claim ingestion.

The current mapping layer accepts malformed aspect fields too broadly. For non-`full` judge results, `_answerability_from_judge_result()` fills empty `missing_aspects` with judge `reasons`, which converts explanatory text into a field that should contain only canonical aspect identifiers. `_validated_answerability()` filters `covered_aspects` to requested aspects, but it does not promote complete source-supported coverage when the raw judge status is `partial`. This can leave a single-aspect watering answer as `partial` and `answerable: false` even when the requested `watering_frequency_or_trigger` aspect is covered with valid source support.

The Gemini judge schema also declares aspect arrays as unconstrained strings. This makes malformed aspect output more likely, although backend normalization must remain the final authority because provider schemas cannot be treated as a complete guarantee.

## Goals / Non-Goals

**Goals:**

- Ensure `covered_aspects` and `missing_aspects` contain only requested canonical `RequiredAspect` values after normalization.
- Ensure judge explanations remain in reason fields and are never copied into aspect arrays.
- Promote raw `partial` output to `full` when validated source support covers all requested aspects and no contradictions are present.
- Preserve true partial behavior for multi-aspect questions where only some requested aspects have valid source support.
- Tighten Gemini judge response schema to reduce malformed aspect arrays at the provider boundary.
- Add regression coverage for malformed missing aspects, complete partial promotion, and true partial preservation.

**Non-Goals:**

- Do not change retrieval, embeddings, web search candidate selection, page fetching, or trusted-source policy.
- Do not change final answer prompt policy except through cleaner normalized metadata.
- Do not change persistence rules beyond ensuring existing ingestion receives canonical covered and missing aspects.
- Do not redefine `answerable` for true partial results; `answerable` remains true only when every requested aspect is answerable.
- Do not add migrations, new dependencies, or frontend API changes.

## Decisions

### Sanitize aspect arrays against requested aspects

Filter `covered_aspects` and `missing_aspects` to the requested canonical aspect set in `_validated_answerability()`. Any unknown string, explanatory sentence, duplicated value, or unrequested aspect is ignored for coverage decisions.

Rationale: the requested aspects are the only valid contract for the current answerability decision. This keeps diagnostics and downstream state bounded and predictable.

Alternative considered: allow any `RequiredAspect` enum value even if not requested. This was rejected because unrequested coverage can confuse missing-aspect routing and final answer diagnostics.

### Keep reasons separate from missing aspects

Remove the fallback that copies `reasons` into `missing_aspects` when a non-`full` judge result omits missing aspects.

Rationale: `missing_aspects` is structured metadata, while `reasons` is explanatory text. Mixing the two creates the exact trace inconsistency this change fixes.

Alternative considered: parse reason text to infer aspect IDs. This was rejected as brittle and unnecessary because requested aspects already define the canonical missing set after coverage is known.

### Promote complete source-supported partial results

In `_validated_answerability()`, when the raw status is `partial`, valid source support exists, contradictions are absent, and normalized covered aspects include every requested aspect, return `status: "full"`, `answerable: true`, and `missing_aspects: []`.

Rationale: status should reflect normalized coverage, not the raw model label. This directly handles single-aspect watering questions where the judge covers `watering_frequency_or_trigger` but keeps `partial` because it expected a fixed interval instead of accepting a condition-based trigger.

Alternative considered: preserve the raw `partial` status and only clean `missing_aspects`. This was rejected because it leaves `answerable: false` for fully covered evidence and keeps diagnostics misleading.

### Preserve true partial results

When normalized coverage is non-empty but does not include every requested aspect, return `status: "partial"`, `answerable: false`, and compute `missing_aspects` from requested aspects minus covered aspects.

Rationale: multi-aspect questions still need to distinguish source-supported answers from missing details. This preserves the existing partial-answer behavior and safe conservative guidance for uncovered aspects.

Alternative considered: trust raw judge `missing_aspects` after filtering. This was rejected because computing missing aspects from requested minus covered is simpler and avoids inconsistent covered/missing overlap.

### Tighten Gemini judge schema as a prevention layer

Update the Gemini judge response schema so `covered_aspects`, `missing_aspects`, and `source_support[].covered_aspects` use the known `RequiredAspect` enum values.

Rationale: stricter provider schema reduces malformed output before it reaches backend normalization.

Alternative considered: backend-only normalization. Backend normalization is still required, but schema tightening improves provider behavior and trace quality.

## Risks / Trade-offs

- [Risk] A raw judge may label a result `partial` for a valid reason not represented in aspect arrays. → Mitigation: promotion requires complete requested coverage, valid source support, and no contradictions; malformed or unsupported outputs still degrade.
- [Risk] Filtering unknown aspect strings could hide provider prompt/schema issues. → Mitigation: reason text remains available, and tests should assert sanitized diagnostics rather than silently accepting malformed aspect fields.
- [Risk] Gemini schema enum tightening may reject provider output that previously parsed. → Mitigation: only constrain fields that are explicitly defined as aspect identifiers; backend normalization remains defensive.
- [Risk] Complete partial promotion could alter fallback routing by avoiding unnecessary web/clarification paths. → Mitigation: this is intended only when all requested aspects are source-supported and should reduce false negatives.

## Migration Plan

Implement as a backend-only change with no data migration. Deploy with the existing test suite covering assistant answerability, web fallback, safety-sensitive validation, contradictory evidence, and provider schema behavior.

Rollback is a code revert. Existing persisted records do not require correction because this change affects runtime normalization and future validated-claim metadata.

## Open Questions

None.
