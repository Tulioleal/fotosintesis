## Why

Assistant web fallback can produce internally inconsistent answerability metadata when the judge returns malformed or overly conservative aspect fields. This is visible in traces where `covered_aspects` includes the requested watering aspect, while `answerable` remains false and `missing_aspects` contains free-form explanations instead of canonical aspect IDs.

This makes diagnostics misleading and can cause downstream answer synthesis, source attribution, or validated-claim ingestion to treat already-covered aspects as missing. The issue should be fixed now because fallback paths are already expensive and slow; inconsistent judge normalization makes those paths harder to debug and less reliable.

## What Changes

- Normalize judge `covered_aspects` and `missing_aspects` against the requested canonical `RequiredAspect` values before downstream use.
- Stop copying judge `reasons` into `missing_aspects`; explanatory text remains only in `reason`/`reasons` fields.
- Promote structurally valid single-aspect or complete multi-aspect `partial` judge output to `full` when all requested aspects are covered, source support is valid, and contradictions are absent.
- Preserve `partial` only for true partial coverage where at least one requested aspect remains uncovered after normalization.
- Tighten the Gemini judge response schema so aspect arrays are constrained to known required-aspect identifiers where supported by the provider schema.
- Keep retrieval, web search selection, fallback routing, final answer generation policy, and evidence persistence policy otherwise unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `assistant-agent`: Care answer diagnostics and aspect-gated synthesis must use normalized canonical aspect metadata and coherent answerability status before final answer generation.
- `knowledge-rag-acquisition`: Runtime evidence validation must structurally sanitize judge aspect fields and promote complete source-supported coverage even when the raw judge status is `partial`.

## Impact

- Affected backend code: `backend/app/assistant/graph.py` answerability mapping and validation helpers.
- Affected provider code: `backend/app/providers/gemini.py` judge response schema.
- Affected tests: assistant answerability normalization, web fallback partial/full behavior, multi-aspect partial behavior, and Gemini judge schema coverage if provider schema tests exist.
- No API shape changes are expected; existing diagnostic fields become cleaner and more internally consistent.
- No database migrations, dependency changes, or frontend changes are expected.
