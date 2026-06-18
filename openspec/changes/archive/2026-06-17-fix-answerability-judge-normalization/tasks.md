## 1. Answerability Normalization

- [x] 1.1 Update `_answerability_from_judge_result()` so judge `reasons` are never copied into `missing_aspects`.
- [x] 1.2 Update `_validated_answerability()` to filter `covered_aspects` and `missing_aspects` to requested canonical `RequiredAspect` values only.
- [x] 1.3 Update `_validated_answerability()` to compute missing aspects from requested aspects minus normalized covered aspects.
- [x] 1.4 Promote raw `partial` results to normalized `full` when all requested aspects are covered, source support is valid, and contradictions are absent.
- [x] 1.5 Preserve normalized `partial` results when only some requested aspects have valid source support.

## 2. Provider Schema Hardening

- [x] 2.1 Tighten the Gemini judge response schema so top-level `covered_aspects` uses the `RequiredAspect` enum values.
- [x] 2.2 Tighten the Gemini judge response schema so top-level `missing_aspects` uses the `RequiredAspect` enum values.
- [x] 2.3 Tighten the Gemini judge response schema so `source_support[].covered_aspects` uses the `RequiredAspect` enum values.

## 3. Regression Tests

- [x] 3.1 Add a unit test proving `_answerability_from_judge_result()` does not copy judge reasons into `missing_aspects`.
- [x] 3.2 Add a regression test where raw `partial` output with full single-aspect watering coverage and malformed missing-aspect text normalizes to `full`, `answerable: true`, and `missing_aspects: []`.
- [x] 3.3 Add a multi-aspect regression test proving true partial coverage remains `partial` and missing aspects contain only uncovered canonical requested aspects.
- [x] 3.4 Add or update provider schema tests proving Gemini judge aspect arrays are enum-constrained, if provider schema tests exist.

## 4. Verification

- [x] 4.1 Run the focused assistant agent tests covering answerability normalization and web fallback behavior.
- [x] 4.2 Run the focused provider tests covering Gemini schema generation or parsing when available.
- [x] 4.3 Run the broader backend test subset affected by assistant answerability, safety-sensitive validation, contradictory evidence, and low-confidence web fallback behavior.
- [x] 4.4 Confirm OpenSpec validation/status reports the change as ready for implementation completion.
