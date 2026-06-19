## Context

The assistant currently uses an LLM classifier for multilingual plant-care routing, then falls back to deterministic classification or clarification when the classifier fails validation, times out, or providers fail. That deterministic fallback has grown into a parallel semantic classifier that maps botanical keywords to detailed care topics and required aspects.

The richer required-aspect taxonomy makes this unsafe to maintain. Detailed botanical classification should remain owned by the validated LLM classifier path, including provider fallback and repair. Deterministic logic remains valuable only for explicit safety and routing cases that do not require botanical interpretation.

## Goals / Non-Goals

**Goals:**

- Preserve successful LLM classifier behavior, including detailed `topic` and `required_aspects` output.
- Preserve classifier provider fallback and one repair retry before using deterministic fallback.
- Replace deterministic semantic botanical fallback with a minimal routing fallback.
- Prevent fallback paths from emitting domain-specific required aspects such as watering, light, diagnosis, pest, repotting, or toxicity aspects.
- Expose diagnostics that distinguish classifier timeout, invalid output, provider failure, and minimal routing fallback usage.

**Non-Goals:**

- Remove the LLM classifier.
- Remove provider fallback or JSON/schema repair.
- Add a second rules-based classifier for botanical topics or domain-qualified required aspects.
- Expand the taxonomy or infer detailed botanical aspects from keywords.

## Decisions

1. Keep the LLM classifier as the only semantic botanical classifier.

   The validated LLM classifier remains authoritative for detailed `CareTopic` and `RequiredAspect` values. Low-confidence but schema-valid LLM output continues to route normally, with confidence retained only as metadata. This avoids replacing one semantic classifier with another.

   Alternative considered: maintain a reduced keyword map for common care topics. Rejected because even a reduced map would still diverge from the LLM classifier and expanded taxonomy.

2. Introduce a minimal deterministic routing fallback.

   The fallback only emits explicit routes that are safe to identify without botanical semantic interpretation: `unsafe_or_injection`, `reminder_request`, `light_measurement_question`, `plant_identification_question`, `out_of_domain`, and `plant_care_question_unknown`.

   Alternative considered: route every classifier failure to clarification. Rejected because existing explicit action routes and safety handling can remain deterministic without semantic botanical risk.

3. Represent unknown plant-care fallback conservatively.

   When fallback detects plant context or obvious botanical language but cannot rely on a valid LLM classification, it uses `plant_care_question_unknown`. The route either asks a concise clarification question or degrades to `topic: "general_care"` and `required_aspects: ["general_care_summary"]` where a classifier-shaped object is required by downstream code.

   Alternative considered: infer `watering`, `light`, `diagnosis`, or other topics from keywords. Rejected because those are detailed semantic decisions and must come only from the LLM classifier.

4. Keep fallback diagnostics explicit and bounded.

   Logs and response diagnostics should distinguish `llm_classifier_timeout`, `llm_classifier_invalid_output`, `llm_classifier_provider_failure`, and `minimal_routing_fallback_used`. The fallback provenance should be visible to diagnostics but not presented prominently in user-facing prose.

   Alternative considered: reuse existing generic classifier failure metadata only. Rejected because operators need to distinguish true semantic classifications from degraded routing during provider outages.

## Risks / Trade-offs

- Classifier outage can reduce answer specificity -> Mitigate with provider fallback, repair retry, concise clarification, and conservative `general_care_summary` only where needed.
- Some requests that previously received guessed detailed answers may require another user turn -> Mitigate by keeping clarification short and preserving explicit routes for reminders, light measurement, identification, safety, and out-of-domain handling.
- Downstream code may assume plant-care classifications always include specific aspects -> Mitigate by allowing only `general_care_summary` for unknown plant-care fallback and updating tests for degraded routing.
- Diagnostics could be confused with semantic fallback reasons -> Mitigate by storing minimal routing fallback provenance separately or with clearly named classifier fallback reason codes.
