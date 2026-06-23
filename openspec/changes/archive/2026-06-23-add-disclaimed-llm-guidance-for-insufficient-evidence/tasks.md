## 1. Answer Mode Eligibility

- [x] 1.1 Inspect `generate_answer`, answerability state fields, safety helpers, diagnostics, and existing fallback paths to identify the smallest insertion point for `general_guidance_with_disclaimer`.
- [x] 1.2 Add an eligibility helper that uses canonical `required_aspects`, `covered_aspects`, `missing_aspects`, answerability status, available evidence/context state, and aspect metadata safety boundaries without user-text keyword matching.
- [x] 1.3 Ensure full answerability still routes to the existing grounded answer path without setting general-guidance diagnostics.
- [x] 1.4 Ensure missing safety-sensitive aspects keep the existing conservative safety fallback unless direct source-supported evidence covers the specific safety claim.

## 2. Disclaimed Guidance Generation

- [x] 2.1 Add a dedicated disclaimed-guidance prompt or prompt builder that preserves `answer_language` and requires explicit separation between validated facts, unvalidated general guidance, limitations, and requests for missing details.
- [x] 2.2 Implement the `generate_answer` branch that uses the disclaimed-guidance generator for eligible insufficient or incomplete non-safety plant-care cases.
- [x] 2.3 Include validated source-supported facts and source metadata only where `source_support` or covered evidence exists, and prohibit citations for generated general guidance.
- [x] 2.4 Add non-destructive pest-care guidance constraints, including inspection, isolation, gentle removal, and photo/detail requests, while prohibiting unsupported insecticide instructions.

## 3. Diagnostics And Persistence Boundaries

- [x] 3.1 Add `llm_general_guidance_used` to bounded assistant care diagnostics and set it only when the disclaimed-guidance branch is used.
- [x] 3.2 Keep `_judge_answerability` behavior strict and avoid changing answerability normalization to make incomplete evidence look validated.
- [x] 3.3 Keep `_validated_claim_payloads` derived only from final normalized `source_support` and ensure generated guidance text is never included in `source_support` or ingestion payloads.
- [x] 3.4 Ensure insufficient disclaimed-guidance answers emit no ingestion claims and do not schedule knowledge ingestion.

## 4. Regression Tests

- [x] 4.1 Add a pest-question test where relevant plant context exists but answerability is insufficient, verifying the answer provides useful disclaimed guidance instead of a generic fallback.
- [x] 4.2 Add a test verifying `llm_general_guidance_used: true`, canonical missing/covered aspect diagnostics, and no prompt/raw evidence leakage for the disclaimed-guidance path.
- [x] 4.3 Add a test proving unvalidated general guidance is not emitted as `ingestion_claims`, is not added to `source_support`, and does not trigger validated-claim ingestion.
- [x] 4.4 Add a partial-evidence test proving source-supported claims can still produce ingestion payloads only from validated `source_support` while the general-guidance section remains excluded.
- [x] 4.5 Add a safety-sensitive test proving unsupported toxicity, pet/child safety, edibility, chemical dosing, severe diagnosis, or pesticide-instruction claims stay on the conservative fallback path.
- [x] 4.6 Add a multilingual or paraphrased non-English regression proving the path relies on schema-validated classifier/aspect state and semantic judging, not deterministic keyword matching.

## 5. Verification

- [x] 5.1 Run the targeted assistant backend tests covering answerability, web fallback, diagnostics, and ingestion payload behavior.
- [x] 5.2 Run the relevant backend test suite or documented subset for assistant chat regressions.
- [x] 5.3 Run OpenSpec validation for this change and fix any artifact or spec-format issues.
