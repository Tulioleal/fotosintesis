## Context

The assistant already routes plant-care questions through confirmed taxonomy, multilingual classification, RAG retrieval, answerability judging, optional trusted web fallback, and answer generation. The current strict path correctly prevents unsupported claims from being treated as validated evidence, but insufficient or incomplete evidence can collapse to clarification or generic fallback even when the request is low-risk and useful plant context exists.

The implementation must preserve the separation between validated source-supported claims and runtime model guidance. Model-generated general guidance can improve UX, but it must remain clearly labeled, uncited, diagnostics-visible, and excluded from `source_support`, `ingestion_claims`, and persistent knowledge.

## Goals / Non-Goals

**Goals:**

- Produce useful answers for low-risk plant-care questions when evidence is relevant but not fully answerable.
- Clearly distinguish validated evidence from non-validated general guidance in the final answer.
- Keep answerability judging, source support normalization, and validated-claim extraction strict.
- Expose `llm_general_guidance_used: true` in diagnostics when this runtime-only mode is used.
- Add tests for pest-care insufficient-evidence behavior and for preventing unvalidated guidance from becoming ingestion claims.

**Non-Goals:**

- Do not loosen retrieval, answerability, trusted-source, or RAG ingestion policies.
- Do not persist final assistant prose or model-generated guidance as knowledge.
- Do not cite general guidance or include it in validated `source_support`.
- Do not provide unsupported toxicity, edibility, pet/child safety, medical-like exposure, severe diagnosis, chemical dosing, pesticide, or other safety-sensitive claims.
- Do not add deterministic keyword lists or language-specific heuristics for semantic plant-care classification or coverage.

## Decisions

1. Add a separate disclaimed-guidance generation path after strict answerability decisions.

The `generate_answer` flow should keep existing full and grounded partial paths. When `sufficient` is false, no safety-sensitive aspect is missing, and either retrieved chunks, web evidence, validated source support, covered aspects, or confirmed plant context indicate the request is still plant-relevant, it can call a new disclaimed guidance generator instead of falling through to generic clarification. This keeps the answer mode explicit rather than weakening `_judge_answerability`.

Alternative considered: relax answerability validation so more results count as partial. This is rejected because it would blur the difference between validated evidence and useful but unsupported advice, and could accidentally affect ingestion.

2. Use aspect metadata and existing classifier output for eligibility and safety boundaries.

Eligibility should be based on existing structured state: canonical `required_aspects`, answerability status, missing/covered aspects, evidence availability, and safety-sensitive metadata. Deterministic checks are acceptable for enum/schema/state boundaries and safety gating, but not for multilingual botanical meaning. Safety-sensitive missing aspects must keep the current conservative fallback unless a specific claim is directly source-supported.

Alternative considered: inspect user text for words such as pest, insect, poison, pet, or child. This is rejected because multilingual semantic routing belongs to the classifier and aspect metadata, not keyword matching.

3. Add a dedicated prompt for `general_guidance_with_disclaimer`.

The prompt should receive the original question, plant context, answer language, validated source-supported facts, missing aspects, sources, and explicit constraints. It should require sections or wording that state what the sources validated, what they did not validate, and which guidance is general model knowledge. It should prohibit citations for the general guidance section and prohibit unsupported safety-sensitive claims.

Alternative considered: reuse the grounded-answer prompt with extra limitations. This is rejected because grounded prompts are optimized to answer from evidence, while this mode must explicitly allow but label non-validated general guidance.

4. Keep validated claim payload creation unchanged or stricter.

`_validated_claim_payloads` should continue deriving ingestion candidates only from normalized `source_support` for `full` or safe `partial` results. The disclaimed guidance path should either leave `ingestion_claims` empty or allow only existing source-supported payloads when the state already contains valid `source_support` for covered aspects. It must never create payloads from generated guidance text.

Alternative considered: store disclaimed guidance with a low confidence marker for future retrieval. This is rejected because it would contaminate RAG with model-generated facts.

5. Add diagnostics without exposing prompts or raw evidence.

Diagnostics should include a boolean `llm_general_guidance_used`, defaulting to false or omitted when not used, and true when the disclaimed guidance branch generates the answer. Existing bounded diagnostics should continue to omit raw prompts, raw model reasoning, full evidence text, and provider internals.

Alternative considered: encode the mode only in fallback reasons. This is rejected because clients and tests need a direct, stable diagnostic signal.

## Risks / Trade-offs

- General guidance may sound more certain than intended -> The prompt must require explicit disclaimer language and separation between validated facts and general guidance.
- Safety-sensitive advice could slip into the general section -> Eligibility must block this mode when missing aspects are safety-sensitive, and the prompt must prohibit unsupported safety claims, chemical dosing, pesticide instructions, edibility, toxicity, and medical-style exposure advice.
- Ingestion contamination could occur if generated text is reused as support -> Tests must assert insufficient disclaimed answers produce no unvalidated `ingestion_claims`, and claim payloads remain derived only from `source_support`.
- Answers may become verbose -> The prompt should ask for concise guidance and a short request for missing details such as close photos, location, symptoms, or treatment history.
- Multilingual output could drift -> The new prompt must preserve `answer_language` like grounded and fallback response generation.

## Migration Plan

No data migration is needed. Deploy as a backend behavior change with tests; rollback is the removal or disabling of the disclaimed-guidance branch and diagnostic field while leaving strict answerability and ingestion code unchanged.

## Open Questions

None.
