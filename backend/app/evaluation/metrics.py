from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.evaluation.dataset import EvaluationCase, VisualCandidate


BERTSCORE_LANGUAGE = "en"


class EvaluationMetricError(RuntimeError):
    pass


def retrieval_recall_at_k(expected_ids: Iterable[str], retrieved_ids: Iterable[str], k: int = 5) -> float | None:
    expected = set(expected_ids)
    if not expected:
        return None
    top_k = set(list(retrieved_ids)[:k])
    return len(expected & top_k) / len(expected)


def precision_at_k(expected_ids: Iterable[str], retrieved_ids: Iterable[str], k: int = 5) -> float | None:
    expected = set(expected_ids)
    top_k = list(retrieved_ids)[:k]
    if not top_k:
        return None
    return len(expected & set(top_k)) / len(top_k)


def rouge_l(reference: str, candidate: str) -> float:
    reference_tokens = _tokens(reference)
    candidate_tokens = _tokens(candidate)
    if not reference_tokens or not candidate_tokens:
        return 0.0
    lcs = _lcs_length(reference_tokens, candidate_tokens)
    precision = lcs / len(candidate_tokens)
    recall = lcs / len(reference_tokens)
    return _f1(precision, recall)


def bertscore(reference: str, candidate: str) -> dict[str, float]:
    if not reference.strip() or not candidate.strip():
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    precision, recall, f1 = _run_bert_score([candidate], [reference])
    return {
        "precision": _as_float(precision[0]),
        "recall": _as_float(recall[0]),
        "f1": _as_float(f1[0]),
    }


def tool_success_rate(calls: list[dict[str, Any]]) -> float | None:
    if not calls:
        return None
    return sum(1 for call in calls if call.get("success")) / len(calls)


def tool_assertion_metrics(
    calls: list[dict[str, Any]], assertions: list[Any]
) -> dict[str, float | None]:
    """Compare observed tool calls against expected tool assertions.

    ``assertions`` are dataset ``ToolAssertion`` records expressing expected
    tool behavior. Observed calls carry name/success. A case passes the tool
    assertion when every expected tool was observed and succeeded as expected.
    """
    expected = [a for a in assertions if a.expected]
    if not expected:
        return {"tool_assertion_satisfaction": None}
    by_name: dict[str, bool] = {call.get("name"): bool(call.get("success")) for call in calls}
    satisfied = 0
    for assertion in expected:
        observed_success = by_name.get(assertion.name)
        if observed_success is None:
            continue
        if observed_success == assertion.expected_success:
            satisfied += 1
    return {"tool_assertion_satisfaction": satisfied / len(expected)}


def visual_metrics(cases: list[EvaluationCase]) -> dict[str, float | None]:
    visual_cases = [case for case in cases if case.expected_scientific_name]
    if not visual_cases:
        return {
            "top_1_accuracy": None,
            "top_3_accuracy": None,
            "taxonomy_validation_rate": None,
            "low_confidence_detection_rate": None,
        }
    return {
        "top_1_accuracy": _ratio(sum(_top_n_match(case.visual_candidates, case.expected_scientific_name, 1) for case in visual_cases), len(visual_cases)),
        "top_3_accuracy": _ratio(sum(_top_n_match(case.visual_candidates, case.expected_scientific_name, 3) for case in visual_cases), len(visual_cases)),
        "taxonomy_validation_rate": _ratio(sum(_taxonomy_validated(case.visual_candidates, case.expected_scientific_name) for case in visual_cases), len(visual_cases)),
        "low_confidence_detection_rate": _ratio(sum(_low_confidence_detected(case) for case in visual_cases), len(visual_cases)),
    }


@dataclass(frozen=True)
class EvaluationProfile:
    """Configured per-case and aggregate approval thresholds.

    Every threshold is either ``None`` (metric observed but ungated) or a
    strictly positive number. ``0.0`` is invalid configuration: an enforced
    profile must never silently disable a gate by zeroing it.
    """

    name: str = "default"
    bertscore_f1: float | None = None
    rouge_l: float | None = None
    retrieval_recall_at_5: float | None = None
    retrieval_precision_at_5: float | None = None
    tool_success_rate: float | None = None
    tool_assertion_satisfaction: float | None = 1.0
    judge_score: float | None = None
    aggregate_pass_rate: float | None = None
    min_supported_case_ratio: float = 0.25


DEFAULT_EVALUATION_PROFILE = EvaluationProfile()

# Enforced chat-answer quality gate: LLM-judge pass rate over supported seed
# cases must reach the product target (60%). Per-case judge scoring follows the
# shared rubric passing score. Other metrics stay observed-but-ungated until
# calibrated baselines exist.
#
# The supported-case floor is calibrated just under today's executable share
# (12 of 50 seed cases = 0.24): it exists to catch silent dataset shrinkage,
# not to mandate growth. Raise it as unsupported flows ship.
QUALITY_GATE_PROFILE = EvaluationProfile(
    name="quality_gate",
    tool_assertion_satisfaction=1.0,
    judge_score=0.75,
    aggregate_pass_rate=0.60,
    min_supported_case_ratio=0.20,
)

_THRESHOLD_FIELDS = (
    "bertscore_f1",
    "rouge_l",
    "retrieval_recall_at_5",
    "retrieval_precision_at_5",
    "tool_success_rate",
    "tool_assertion_satisfaction",
    "judge_score",
    "aggregate_pass_rate",
)


class EvaluationProfileError(ValueError):
    """Raised when an evaluation profile contains invalid configuration."""


def validate_profile(profile: EvaluationProfile) -> None:
    """Reject profiles that gate nothing by zero or misuse the floor."""
    for field_name in _THRESHOLD_FIELDS:
        value = getattr(profile, field_name)
        if value is not None and float(value) <= 0:
            raise EvaluationProfileError(
                f"Evaluation profile {profile.name!r} sets {field_name} to "
                f"{value}. Thresholds must be strictly positive or omitted."
            )
    if not 0 < float(profile.min_supported_case_ratio) <= 1:
        raise EvaluationProfileError(
            f"Evaluation profile {profile.name!r} sets "
            f"min_supported_case_ratio to {profile.min_supported_case_ratio}; "
            "it must be within (0, 1]."
        )


def apply_per_case_thresholds(
    scores: dict[str, Any],
    profile: EvaluationProfile = DEFAULT_EVALUATION_PROFILE,
) -> list[str]:
    """Return the list of threshold failures for a single case.

    Only scores that were actually computed are checked. A threshold with no
    corresponding score (e.g. no reference text) is not applied.
    """
    failures: list[str] = []
    _check_threshold(failures, scores, "bertscore", "f1", profile.bertscore_f1, "bertscore_f1")
    _check_threshold(failures, scores, "rouge_l", None, profile.rouge_l, "rouge_l")
    _check_threshold(failures, scores, "retrieval_recall@5", None, profile.retrieval_recall_at_5, "retrieval_recall@5")
    _check_threshold(failures, scores, "precision@5", None, profile.retrieval_precision_at_5, "precision@5")
    _check_threshold(failures, scores, "tool_success_rate", None, profile.tool_success_rate, "tool_success_rate")
    _check_threshold(failures, scores, "tool_assertion_satisfaction", None, profile.tool_assertion_satisfaction, "tool_assertion_satisfaction")
    judge = scores.get("judge")
    if isinstance(judge, dict):
        judge_score = judge.get("score")
        if (
            judge_score is not None
            and profile.judge_score is not None
            and float(judge_score) < profile.judge_score
        ):
            failures.append("judge_score")
    return failures


def _check_threshold(
    failures: list[str],
    scores: dict[str, Any],
    score_key: str,
    sub_key: str | None,
    threshold: float | None,
    label: str,
) -> None:
    if threshold is None or threshold <= 0:
        return
    value = scores.get(score_key)
    if isinstance(value, dict) and sub_key is not None:
        value = value.get(sub_key)
    if value is None:
        return
    if float(value) < threshold:
        failures.append(label)


def aggregate_pass_rate_met(pass_rate: float, profile: EvaluationProfile = DEFAULT_EVALUATION_PROFILE) -> bool:
    if profile.aggregate_pass_rate is None:
        return True
    return pass_rate >= profile.aggregate_pass_rate


def evaluate_run_gate(*, summary: dict[str, Any], profile: EvaluationProfile) -> dict[str, Any]:
    """Decide run approval from a completed run summary.

    The pass-rate denominator is the supported cases only (unsupported cases
    are excluded). A supported-case ratio below the profile floor fails the run
    as a coverage failure, distinct from threshold quality failures; execution
    and metric errors also block approval.
    """
    total = int(summary.get("total_cases", 0))
    passed = int(summary.get("passed_cases", 0))
    quality_failures = int(summary.get("quality_failures", 0))
    supported = passed + quality_failures
    ratio = (supported / total) if total else 0.0

    reasons: list[str] = []
    coverage_failure = False

    if ratio < float(profile.min_supported_case_ratio):
        coverage_failure = True
        reasons.append(
            f"coverage failure: supported-case ratio {ratio:.2f} is below the "
            f"configured minimum {float(profile.min_supported_case_ratio):.2f} "
            f"({total - supported} of {total} cases unsupported)"
        )

    if summary.get("execution_errors"):
        reasons.append(f"{summary['execution_errors']} execution error(s)")
    if summary.get("metric_errors"):
        reasons.append(f"{summary['metric_errors']} metric error(s)")

    rate_gate = aggregate_pass_rate_met(float(summary.get("pass_rate", 0.0)), profile)
    if not rate_gate and not coverage_failure:
        reasons.append(
            f"aggregate pass rate {float(summary.get('pass_rate', 0.0)):.2%} is "
            f"below the configured minimum {profile.aggregate_pass_rate:.2%}"
            if profile.aggregate_pass_rate is not None
            else "aggregate gate misconfigured"
        )

    return {
        "approved": not reasons,
        "coverage_failure": coverage_failure,
        "supported_case_ratio": ratio,
        "min_supported_case_ratio": float(profile.min_supported_case_ratio),
        "reasons": reasons,
    }


def _tokens(text: str) -> list[str]:
    return [token.strip(".,;:!?()[]{}\"'").lower() for token in text.split() if token.strip()]


def _run_bert_score(candidates: list[str], references: list[str]) -> Any:
    try:
        from bert_score import score

        return score(candidates, references, lang=BERTSCORE_LANGUAGE, verbose=False)
    except Exception as exc:
        raise EvaluationMetricError(
            "BERTScore could not be computed. Install backend dependencies and ensure the "
            "configured BERTScore model is available."
        ) from exc


def _as_float(value: Any) -> float:
    if hasattr(value, "item"):
        value = value.item()
    return float(value)


def _lcs_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _top_n_match(candidates: list[VisualCandidate], expected: str | None, n: int) -> bool:
    if not expected:
        return False
    normalized = expected.lower()
    return any(candidate.scientific_name.lower() == normalized for candidate in candidates[:n])


def _taxonomy_validated(candidates: list[VisualCandidate], expected: str | None) -> bool:
    if not expected:
        return False
    normalized = expected.lower()
    return any(
        candidate.scientific_name.lower() == normalized and candidate.taxonomy_validated
        for candidate in candidates
    )


def _low_confidence_detected(case: EvaluationCase) -> bool:
    if not case.expected_low_confidence:
        return True
    if not case.visual_candidates:
        return True
    first = case.visual_candidates[0]
    return first.confidence_label in {"low", "inconclusive"} or (first.confidence or 0) < 0.5


__all__ = [
    "BERTSCORE_LANGUAGE",
    "DEFAULT_EVALUATION_PROFILE",
    "QUALITY_GATE_PROFILE",
    "EvaluationMetricError",
    "EvaluationProfile",
    "EvaluationProfileError",
    "aggregate_pass_rate_met",
    "apply_per_case_thresholds",
    "bertscore",
    "evaluate_run_gate",
    "precision_at_k",
    "retrieval_recall_at_k",
    "rouge_l",
    "tool_assertion_metrics",
    "tool_success_rate",
    "validate_profile",
    "visual_metrics",
]
