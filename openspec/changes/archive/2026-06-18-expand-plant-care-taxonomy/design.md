## Context

The assistant already uses a closed classifier contract with `topic` and `required_aspects`, then feeds those values into retrieval, answerability judging, web fallback, answer synthesis, diagnostics, and tests. The current taxonomy includes useful simple care aspects, but some values are generic enough that downstream code must infer their meaning from `CareTopic` or surrounding wording.

This change formalizes `RequiredAspect` as a self-descriptive evidence requirement. A value such as `pest_treatment_action` must carry its own domain, so validators, diagnostics, and web fallback do not need to guess whether a generic `treatment_action` means pest, disease, transplant shock, or safety handling.

## Goals / Non-Goals

**Goals:**

- Make every `RequiredAspect` domain-qualified, except explicitly general values under `general_*`.
- Expand `CareTopic` to cover common plant-care domains without changing the assistant graph architecture.
- Keep classification minimal: select only aspects directly requested, explicitly implied, or necessary to answer the user's wording.
- Preserve aspect-by-aspect answerability validation and expose selected canonical enum values in diagnostics.
- Improve web fallback query terms by converting domain-qualified aspects into natural-language evidence needs.

**Non-Goals:**

- Replace LangGraph orchestration, RAG retrieval, web fallback, ingestion, or answer synthesis architecture.
- Add medical, veterinary, or human-health advice beyond conservative plant-care safety boundaries.
- Force broad care questions to enumerate every possible aspect.
- Persist a new data model or create a database migration unless implementation discovers persisted enum consumers that require compatibility handling.

## Decisions

1. Treat `RequiredAspect` as the primary evidence contract.

   `CareTopic` remains useful for routing, diagnostics, prompts, and retrieval context, but no validator or query builder should need to use topic to understand an aspect's domain. This avoids ambiguous paths such as interpreting `prevention_steps` differently for pests and diseases.

   Alternative considered: keep generic aspects and add topic-specific disambiguation in prompts. This was rejected because it preserves the ambiguity and makes downstream behavior depend on coupled fields.

2. Rename ambiguous aspects instead of keeping legacy names in the canonical enum.

   Canonical output should use explicit values such as `toxicity_pet_safety`, `disease_treatment_action`, `repotting_post_care`, and `diagnosis_triage_steps`. If compatibility is needed for old diagnostics or stored data, implement a narrow translation boundary rather than allowing legacy names in fresh classifier output.

   Alternative considered: keep aliases in the enum. This was rejected for classifier output because it would allow the ambiguity this change is meant to remove.

3. Use classifier guidance plus deterministic helpers to prevent over-selection.

   Symptom questions should usually produce diagnosis aspects; pest, disease, toxicity, or watering aspects should be added only when the user explicitly asks for them or the wording strongly implies them. Broad care questions may use `general_*` aspects rather than selecting many domain-specific details.

   Alternative considered: map symptoms to all likely care causes. This was rejected because it would inflate required evidence, increase fallback usage, and make answerability harder to satisfy.

4. Keep answerability strict and aspect-local.

   Evidence is full only when every requested domain-qualified aspect is directly covered. Diagnosis answers must present causes as hypotheses unless evidence directly supports a definitive claim. Safety-sensitive toxicity and handling aspects continue to require stricter validation thresholds.

   Alternative considered: accept generic care evidence as covering related granular aspects. This was rejected because it would weaken source-backed answer guarantees.

5. Generate web fallback queries from readable aspect labels.

   Query construction should translate underscores and domain terms into natural-language phrases while preserving the confirmed taxonomy, topic, original question, and trusted-source terms. It should not add broad per-aspect expansion beyond the selected missing aspects.

   Alternative considered: one query per missing aspect. This remains out of scope unless the current fallback strategy proves insufficient after this taxonomy expansion.

## Risks / Trade-offs

- Larger enums may confuse the LLM classifier -> Mitigate with explicit prompt rules, examples, deterministic regression tests, and schema repair behavior for unknown enum values.
- Granular aspects may increase partial answerability and web fallback use -> Mitigate by keeping classifier output minimal and using `general_*` for broad requests.
- Renamed values may affect tests or persisted diagnostics -> Mitigate by migrating tests and adding a narrow compatibility map only where persisted legacy values are actually read.
- Keyword-based conservative checks may miss synonyms for new aspects -> Mitigate by updating keyword groups while preserving semantic judging as authoritative.
- Safety aspect renames could accidentally lower validation strictness -> Mitigate by centralizing safety-sensitive aspect detection and testing every toxicity and safety enum family.

## Migration Plan

1. Update canonical enums and prompt examples.
2. Update deterministic classification and helper mappings.
3. Update answerability, validation, query construction, and diagnostics to consume the new values.
4. Update tests and fixtures from legacy aspect names to domain-qualified names.
5. Add compatibility translation only for persisted or externally read legacy diagnostics if implementation confirms they are needed.
6. Roll back by reverting enum and prompt changes together; do not deploy partial enum changes without classifier and validator updates.
