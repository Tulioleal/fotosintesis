## 1. Settings

- [x] 1.1 Add `assistant_strong_answer_validation_threshold: float = 0.30` to `Settings` in `backend/app/core/settings.py`
- [x] 1.2 Add `assistant_judge_timeout_seconds: float = 25.0` to `Settings` in `backend/app/core/settings.py`
- [x] 1.3 Add `assistant_web_search_timeout_seconds: float = 20.0` to `Settings` in `backend/app/core/settings.py`

## 2. Strong Full-Support Detection

- [x] 2.1 Add `_is_strong_full_support(semantic_result, requested_aspects)` helper to `backend/app/assistant/graph.py`
- [x] 2.2 Add `_validation_threshold_for_aspect(aspect, semantic_result, requested_aspects, default_threshold, strong_threshold, safety_threshold)` helper to `backend/app/assistant/graph.py`

## 3. Context-Aware Validation

- [x] 3.1 Update `_validate_evidence_against_required_aspects` in `backend/app/assistant/graph.py` to use `_validation_threshold_for_aspect` instead of `_aspect_meets_threshold`
- [x] 3.2 Update `_aspect_meets_threshold` to accept a threshold parameter or remove it in favor of the new helper

## 4. Judge Timeout

- [x] 4.1 Add `timeout_seconds` parameter to `_judge_answerability` in `backend/app/assistant/graph.py`
- [x] 4.2 Wrap `judge.judge_response` call in `asyncio.wait_for` with the timeout parameter
- [x] 4.3 Return controlled `AnswerabilityResult` with "timed out" reason on `TimeoutError`
- [x] 4.4 Update `evaluate_sufficiency` to pass `timeout_seconds=settings.assistant_judge_timeout_seconds`
- [x] 4.5 Update `fallback_plant_data` to pass `timeout_seconds=settings.assistant_judge_timeout_seconds`
- [x] 4.6 Update `_judge_combined_evidence` to pass `timeout_seconds=settings.assistant_judge_timeout_seconds`

## 5. Web Search Timeout

- [x] 5.1 Wrap `self.tools.trusted_web_search(query)` in `asyncio.wait_for` with `timeout=settings.assistant_web_search_timeout_seconds` in `fallback_web_search`
- [x] 5.2 Return controlled tool failure with "timed out" reason on `TimeoutError`

## 6. Logging

- [x] 6.1 Add structured logging for threshold decisions in `_validate_evidence_against_required_aspects` including aspect, threshold_used, confidence, status, answerable, strong_full_support, safety_sensitive, and validated

## 7. Tests

- [x] 7.1 Add test: low-confidence strong watering support is accepted (confidence 0.35, status full, all aspects covered, source support present)
- [x] 7.2 Add test: low-confidence safety support is rejected (pet_toxicity with confidence 0.35)
- [x] 7.3 Add test: partial low-confidence support is rejected (watering + light, partial status, confidence 0.35)
- [x] 7.4 Add test: high-confidence partial support still works as partial (confidence 0.80)
- [x] 7.5 Add test: judge timeout returns controlled insufficient result
- [x] 7.6 Add test: web search timeout returns controlled fallback

## 8. Verification

- [x] 8.1 Run existing test suite to ensure no regressions
- [x] 8.2 Run new regression tests to verify threshold behavior
- [x] 8.3 Verify Neon Pothos watering question accepts RAG at confidence 0.35 without web fallback
