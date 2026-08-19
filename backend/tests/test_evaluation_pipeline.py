import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import app.evaluation.metrics as metrics
import app.evaluation.runner as runner_module
from app.evaluation import EvaluationRunner, load_seed_cases
from app.evaluation.dataset import EvaluationCase, ToolAssertion
from app.evaluation.metrics import (
    EvaluationMetricError,
    EvaluationProfile,
    apply_per_case_thresholds,
    precision_at_k,
    retrieval_recall_at_k,
    rouge_l,
    tool_assertion_metrics,
    tool_success_rate,
)
from app.evaluation.reconcile import reconcile_cases
from app.evaluation.report import render_markdown_report
from app.providers.types import JudgeResult

from tests._evaluation_helpers import executable_cases, patch_bertscore


class FailingJudgeProvider:
    async def judge_response(
        self,
        payload: dict[str, Any],
        rubric: dict[str, Any],
        **kwargs: Any,
    ) -> JudgeResult:
        return JudgeResult(
            provider="test-judge",
            model="test-model",
            score=0.2,
            passed=False,
            reasons=["Grounding criterion failed."],
        )


def test_seed_dataset_has_50_cases_across_target_flows() -> None:
    cases = load_seed_cases()

    assert len(cases) == 50
    assert {case.flow for case in cases} == {
        "assistant_rag",
        "plant_profile_generation",
        "revive_plant",
        "incremental_knowledge",
        "reminders_agent",
        "light_measurement_context",
        "plant_identification_maas",
    }


def test_reconciliation_marks_non_graph_flows_unsupported() -> None:
    cases = reconcile_cases(load_seed_cases())
    by_id = {case.id: case for case in cases}

    assert by_id["assistant_rag_01"].unsupported is False
    assert by_id["plant_profile_generation_01"].unsupported is True
    assert "plant_profile_generation" in by_id["plant_profile_generation_01"].skip_reason
    assert by_id["incremental_knowledge_01"].unsupported is True
    assert by_id["plant_identification_maas_01"].unsupported is True


def test_retrieval_and_text_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_bert_score(candidates: list[str], references: list[str]) -> tuple[list[float], list[float], list[float]]:
        assert candidates == ["bright light"]
        assert references == ["bright indirect light"]
        return [0.91], [0.82], [0.86]

    monkeypatch.setattr(metrics, "_run_bert_score", fake_bert_score)

    assert retrieval_recall_at_k(["a", "b"], ["a", "c", "b"], k=2) == 0.5
    assert precision_at_k(["a", "b"], ["a", "c", "b"], k=2) == 0.5
    assert rouge_l("water when soil dries", "water soil dries") > 0.75
    assert metrics.bertscore("bright indirect light", "bright light") == {
        "precision": 0.91,
        "recall": 0.82,
        "f1": 0.86,
    }


def test_tool_metrics_from_observed_calls() -> None:
    calls = [
        {"name": "knowledge_search", "success": True},
        {"name": "generate_text", "success": False},
    ]
    assert tool_success_rate(calls) == 0.5

    assertions = [
        ToolAssertion(name="knowledge_search", expected=True, expected_success=True),
        ToolAssertion(name="generate_text", expected=True, expected_success=True),
    ]
    satisfaction = tool_assertion_metrics(calls, assertions)
    assert satisfaction["tool_assertion_satisfaction"] == 0.5


def test_thresholds_apply_every_configured_threshold() -> None:
    scores = {
        "bertscore": {"f1": 0.5},
        "rouge_l": 0.4,
        "retrieval_recall@5": 0.6,
        "precision@5": 0.7,
        "tool_success_rate": 0.8,
        "tool_assertion_satisfaction": 1.0,
        "judge": {"score": 0.5},
    }
    profile = EvaluationProfile(
        bertscore_f1=0.6,
        rouge_l=0.5,
        retrieval_recall_at_5=0.7,
        retrieval_precision_at_5=0.8,
        tool_success_rate=0.9,
        tool_assertion_satisfaction=1.0,
        judge_score=0.6,
    )
    failures = apply_per_case_thresholds(scores, profile)
    assert "bertscore_f1" in failures
    assert "rouge_l" in failures
    assert "retrieval_recall@5" in failures
    assert "precision@5" in failures
    assert "tool_success_rate" in failures
    assert "judge_score" in failures


def test_bertscore_empty_inputs_do_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(candidates: list[str], references: list[str]) -> None:
        raise AssertionError("BERTScore model should not be called for empty inputs")

    monkeypatch.setattr(metrics, "_run_bert_score", fail_if_called)

    assert metrics.bertscore("", "candidate") == {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert metrics.bertscore("reference", "") == {"precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_bertscore_failure_does_not_return_token_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_bert_score(candidates: list[str], references: list[str]) -> None:
        raise EvaluationMetricError("BERTScore unavailable")

    monkeypatch.setattr(metrics, "_run_bert_score", fail_bert_score)

    with pytest.raises(EvaluationMetricError):
        metrics.bertscore("same words", "same words")


def test_report_states_mode_and_separates_error_classes() -> None:
    result = SimpleNamespace(
        id="run-1",
        mode="recorded",
        recording_version=1,
        profile="default",
        summary={
            "total_cases": 3,
            "passed_cases": 1,
            "quality_failures": 1,
            "execution_errors": 1,
            "metric_errors": 0,
            "unsupported": 0,
            "pass_rate": 0.5,
            "aggregate_approved": True,
            "flows": {},
        },
        case_results=[
            SimpleNamespace(
                case_id="c1", status="passed", failures=[], error_category=None, error_detail=None, skip_reason=None
            ),
            SimpleNamespace(
                case_id="c2", status="quality_failure", failures=["low score"], error_category=None, error_detail=None, skip_reason=None
            ),
            SimpleNamespace(
                case_id="c3", status="execution_error", failures=[], error_category="recording", error_detail="missing", skip_reason=None
            ),
        ],
    )

    report = render_markdown_report(result)

    assert "Mode: recorded" in report
    assert "Recording version: 1" in report
    assert "## Execution Errors" in report
    assert "## Quality Failures" in report
    assert "c3" in report
    assert "c2" in report


@pytest.mark.asyncio
async def test_runner_persists_results_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_bertscore(monkeypatch)

    result = await EvaluationRunner(output_dir=tmp_path).run()

    assert result.summary["total_cases"] == 50
    assert result.summary["unsupported"] == 38
    assert result.summary["execution_errors"] == 0
    assert result.report_path is not None
    assert Path(result.report_path).exists()
    assert (tmp_path / result.id / "result.json").exists()
    assert "Mode: recorded" in Path(result.report_path).read_text(encoding="utf-8")

    persisted = json.loads((tmp_path / result.id / "result.json").read_text(encoding="utf-8"))
    assert persisted["mode"] == "recorded"
    assert persisted["profile"] == "default"


@pytest.mark.asyncio
async def test_runner_records_failed_judge_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    case = EvaluationCase(
        id="judge-failure-case",
        flow="assistant_rag",
        input={"prompt": "How should I care for this plant?"},
        setup={"plant_binomial_name": "Monstera deliciosa"},
    )

    result = await EvaluationRunner(
        judge_provider=FailingJudgeProvider(),
        output_dir=tmp_path,
    ).run(cases=[case])

    case_result = result.case_results[0]
    assert case_result.status == "quality_failure"
    assert "Grounding criterion failed." in case_result.failures


@pytest.mark.asyncio
async def test_runner_records_unsatisfied_tool_assertion(tmp_path: Path) -> None:
    case = EvaluationCase(
        id="tool-claim-case",
        flow="reminders_agent",
        input={"prompt": "Create a watering reminder."},
        tool_assertions=[
            ToolAssertion(name="create_reminder", expected=True, expected_success=True),
        ],
    )

    result = await EvaluationRunner(output_dir=tmp_path).run(cases=[case])

    case_result = result.case_results[0]
    # The graph (with the deterministic provider set) does not create a
    # reminder, so the tool assertion is not satisfied.
    assert case_result.status == "quality_failure"
    assert any("tool_assertion_satisfaction" in failure for failure in case_result.failures)
