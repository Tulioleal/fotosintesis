## Context

The assistant backend uses a single evidence validation threshold (`assistant_evidence_validation_threshold = 0.75`) for all RAG judge results. When the answerability judge returns `status: "full"` with `answerable: true` and all aspects covered but confidence below 0.75 (e.g., 0.35 for a watering question), the evidence is rejected as insufficient, triggering an expensive web fallback path. This creates unnecessary latency, increases API costs, and degrades user experience for straightforward botanical questions where the RAG evidence is semantically valid.

Additionally, the `_judge_answerability` and `fallback_web_search` methods have no timeouts, so slow provider calls can exceed frontend timeout limits and cause request failures.

The current validation logic in `_validate_evidence_against_required_aspects` (line 1271) applies a single threshold to all non-safety aspects:

```python
def _aspect_meets_threshold(aspect, confidence, threshold, safety_threshold):
    required = safety_threshold if aspect in SAFETY_SENSITIVE_ASPECTS else threshold
    return confidence >= required
```

This means a structurally full watering answer with confidence 0.35 fails the 0.75 threshold and triggers web search, even though the judge confirmed all aspects are covered with valid source support.

## Goals / Non-Goals

**Goals:**
- Accept structurally strong RAG results (status full, answerable, all aspects covered, source support present, no contradictions) with a lower confidence threshold (0.30).
- Preserve strict safety validation for `pet_toxicity` and `human_edibility` aspects (threshold 0.85).
- Add configurable timeouts for the answerability judge (25s) and web search (20s) to prevent backend requests from exceeding frontend timeouts.
- Add structured logging for threshold decisions to improve debuggability.
- Ensure valid RAG evidence does not trigger unnecessary web fallback.

**Non-Goals:**
- Changing the judge model or prompt.
- Modifying the frontend timeout behavior.
- Changing the combined evidence judge logic for web fallback paths.
- Restructuring the LangGraph nodes or routing.
- Modifying the evidence validation threshold for partial or contradictory results.

## Decisions

### Decision 1: Context-aware threshold selection

**Choice**: Add a `_validation_threshold_for_aspect` helper that selects threshold based on aspect safety sensitivity and structural strength of the judge result.

**Rationale**: The current single-threshold approach treats all non-safety aspects identically, but structurally strong results (full status, all aspects covered, source support present) should be accepted with a lower threshold. This is more precise than adjusting the default threshold for all cases.

**Alternatives considered**:
- Lowering `assistant_evidence_validation_threshold` globally: Rejected because it weakens validation for partial/ambiguous results.
- Adding a boolean flag for "strong results": Rejected because it doesn't provide enough granularity for future tuning.

### Decision 2: Strong full-support detection

**Choice**: Add an `_is_strong_full_support` helper that checks:
- `semantic_result.status == "full"`
- `semantic_result.answerable is True`
- All requested aspects are in `covered_aspects`
- `source_support` is non-empty
- `contradictions` is empty

**Rationale**: This provides a clear, testable definition of "structurally strong" that can be used to select the lower threshold. The helper keeps the threshold decision explainable and testable.

### Decision 3: Timeout implementation

**Choice**: Wrap `judge.judge_response` and `self.tools.trusted_web_search` calls in `asyncio.wait_for` with configurable timeouts from settings.

**Rationale**: Already done for the care classifier. Same pattern ensures consistency. Timeout errors return controlled results rather than propagating exceptions.

**Alternatives considered**:
- Using `asyncio.timeout` context manager: Same effect, but `wait_for` is more explicit for cancellation semantics.
- Setting timeouts at the HTTP client level: Rejected because it doesn't cover model inference time.

### Decision 4: Threshold defaults

**Choice**: 
- `assistant_strong_answer_validation_threshold = 0.30`
- `assistant_judge_timeout_seconds = 25.0`
- `assistant_web_search_timeout_seconds = 20.0`

**Rationale**: 0.30 is low enough to accept strong watering answers (observed confidence 0.35) while high enough to reject genuinely weak evidence. Judge timeout at 25s prevents the observed 272s calls. Web search timeout at 20s prevents fallback from hanging.

## Risks / Trade-offs

- **[Risk] Lower threshold accepts weak evidence**: Mitigated by requiring all structural checks (status full, answerable, all aspects covered, source support present, no contradictions) before using the lower threshold. Partial or ambiguous results still use the default 0.75 threshold.

- **[Risk] Timeouts cause premature failures**: Mitigated by returning controlled `AnswerabilityResult` with descriptive reason strings, and by logging timeout events for monitoring. Timeouts are configurable per deployment.

- **[Risk] Combined judge path still runs unnecessarily**: Mitigated by ensuring `evaluate_sufficiency` returns `sufficient: True` when RAG is strong, which prevents the web fallback path from being triggered. Regression test ensures this behavior.

- **[Trade-off] Three thresholds instead of one**: Increases configuration complexity but provides necessary granularity for safety vs. non-safety vs. strong-structure cases.
