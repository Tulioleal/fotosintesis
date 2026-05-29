from collections.abc import Iterable
from typing import Any

from app.evaluation.dataset import EvaluationCase, ToolTrace, VisualCandidate


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


def tool_metrics(traces: list[ToolTrace]) -> dict[str, float | None]:
    called = [trace for trace in traces if trace.called]
    expected = [trace for trace in traces if trace.expected]
    unnecessary = [trace for trace in called if not trace.expected]
    failed_claims = [trace for trace in traces if not trace.success and trace.claimed_success]
    return {
        "tool_success_rate": _ratio(sum(1 for trace in called if trace.success), len(called)),
        "unnecessary_web_search_rate": _ratio(
            sum(1 for trace in unnecessary if trace.name == "web_search"),
            max(1, len(called)),
        ),
        "failed_action_claim_rate": _ratio(len(failed_claims), max(1, len(expected))),
    }


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
