## Context

`RequiredAspect` is the canonical contract for plant-care evidence requirements, but the semantics for each aspect are currently distributed across `care_contracts.py`, `graph.py`, validation guidance, targeted web search query construction, safety-sensitive threshold selection, and diagnostics. The existing taxonomy is already domain-qualified and includes safety, diagnosis, watering, disease, pest, taxonomy, and ecology aspects, so adding more aspects will require a reusable way to keep semantics consistent across the assistant pipeline.

The change must preserve enum values as canonical identifiers because classifier schemas, judge normalization, response diagnostics, tests, and persisted metadata depend on stable aspect strings. The registry should therefore describe aspects without replacing the enum.

## Goals / Non-Goals

**Goals:**

- Add a typed metadata registry keyed by `RequiredAspect`.
- Make answerability guidance, web fallback query terms, safety sensitivity, and readable diagnostic labels consume registry metadata.
- Keep metadata concise, with `coverage_guidance` only for aspects where the enum name is insufficient or false positives/false negatives are likely.
- Preserve safe fallback behavior when metadata is missing or an unknown aspect string is encountered.
- Cover high-risk aspects first, especially watering trigger semantics, diagnosis, pest/disease treatment, repotting shock risk where present, toxicity, and poison-control/vet escalation.

**Non-Goals:**

- Replacing the `RequiredAspect` enum or classifier contract.
- Making the classifier deterministic or changing provider fallback behavior.
- Encoding all botanical care knowledge in metadata.
- Reworking RAG retrieval, web fallback architecture, or provider interfaces.
- Requiring verbose guidance for every aspect.

## Decisions

1. Introduce `backend/app/assistant/aspect_metadata.py` as the source of aspect semantics.

   The module will define a frozen `RequiredAspectMetadata` dataclass and a `REQUIRED_ASPECT_METADATA` mapping keyed by `RequiredAspect`. Keeping metadata outside `graph.py` avoids another large hardcoded structure in orchestration code and makes unit testing simpler. Alternative considered: attach properties to the enum. That was rejected because it would make `care_contracts.py` a large semantic registry and blur the boundary between canonical identifiers and pipeline behavior.

2. Keep `RequiredAspect` as the canonical identifier and make metadata lookup tolerant.

   `metadata_for_aspect(aspect: RequiredAspect | str)` will accept enum members or strings, translate known legacy aspect values where appropriate at call sites, and return `None` for unknown values. Callers will fall back to enum-derived labels or the original aspect string rather than raising. Alternative considered: require every lookup to raise on missing metadata. That would catch registry gaps earlier, but it would make fallback paths brittle and conflict with the existing validation behavior for unknown or legacy values.

3. Move existing answerability guidance into metadata and expose lookup helpers.

   The registry helper functions will include `aspect_validation_guidance()`, `aspect_query_terms()`, and `is_safety_sensitive_aspect()`. Existing `_aspect_validation_guidance()` in `graph.py` should become a thin wrapper or be replaced by the helper. Alternative considered: keep specialized dictionaries for each behavior and only add labels. That was rejected because it preserves the drift risk this change is meant to remove.

4. Web fallback query construction will combine metadata query labels and search terms.

   `_targeted_web_query()` should derive aspect text from `query_label` and/or `search_terms` for missing aspects, dedupe terms, and fall back to the enum value with underscores replaced. This keeps queries readable and aspect-specific without changing the search provider interface. Alternative considered: use only `search_terms`. That may over-expand queries; using `query_label` first keeps a concise primary phrase while terms provide targeted context.

5. Safety sensitivity will be metadata-driven while preserving the existing exported constant during migration.

   The registry should mark safety-sensitive toxicity and safety aspects. `SAFETY_SENSITIVE_ASPECTS` can remain exported for compatibility but should be derived from metadata or replaced at usage sites by `is_safety_sensitive_aspect()` where practical. Alternative considered: delete the constant immediately. That risks breaking imports and tests without improving behavior.

6. The registry will not provide evidence coverage keywords.

   Metadata must not include deterministic evidence keywords or any field whose purpose is to decide whether evidence covers an aspect. Snippet and content eligibility should remain limited to non-semantic checks such as valid URL, trusted source selection, and non-empty text presence; the semantic answerability judge decides coverage. Alternative considered: keep cheap keyword prefiltering in metadata. That was rejected because it is brittle for multilingual evidence, synonyms, spelling variants, and source phrasing.

7. Diagnostics may add readable labels but must preserve canonical values.

   Diagnostic metadata can include labels derived from metadata when useful, but existing `required_aspects`, `covered_aspects`, and `missing_aspects` must remain canonical enum values. Alternative considered: replace diagnostics with labels. That would harm machine readability and break existing consumers.

## Risks / Trade-offs

- Registry growth could become hard to maintain -> Keep fields concise, require guidance only when ambiguity or risk justifies it, and test representative high-risk aspects.
- Prompt payloads could grow if every aspect has guidance -> Include guidance only for requested aspects and only when `coverage_guidance` is defined.
- Web retrieval behavior may shift due to new query terms -> Preserve scientific name, user question context, trusted-source suffix, and enum fallback terms.
- Incomplete metadata could create uneven behavior -> Missing metadata must fall back safely, and tests should cover an unmapped aspect path.
- Derived safety sensitivity could diverge from existing constants during migration -> Either derive the compatibility constant from metadata or assert equivalence in tests until usage sites are migrated.

## Migration Plan

1. Add the metadata module, dataclass, registry, and helper functions.
2. Move existing coverage guidance entries into registry metadata and keep compatibility imports only where needed.
3. Update judge payload construction to call metadata-driven guidance helpers.
4. Update targeted web query construction to use metadata query labels and search terms.
5. Remove deterministic keyword gates from snippet/content eligibility so trusted evidence reaches the semantic answerability judge without keyword matching.
6. Update safety-sensitive threshold and fallback checks to use metadata-driven safety helpers where practical.
7. Add or update tests for metadata lookup, guidance payloads, web query terms, safety thresholds, non-English evidence reaching the judge, diagnostic labels if added, and missing-metadata fallback.

Rollback is straightforward because the change is code-only: callers can temporarily fall back to the previous local dictionaries and hardcoded safety set if registry behavior causes unexpected retrieval or validation regressions.

## Open Questions

- Whether response diagnostics should expose an additional `aspect_labels` field immediately or defer readable labels to structured logs first.
- Whether the registry should initially cover every current `RequiredAspect` with at least minimal labels and search terms, or introduce complete metadata incrementally while relying on safe fallbacks for lower-risk aspects.
