import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import app.evaluation.metrics as metrics
import app.evaluation.runner as runner_module
from app.evaluation import EvaluationRunner, load_seed_cases
from app.evaluation.dataset import EvaluationCase, ToolTrace
from app.evaluation.metrics import EvaluationMetricError, precision_at_k, retrieval_recall_at_k, rouge_l
from app.evaluation.report import render_markdown_report
from app.providers.types import JudgeResult


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


def test_report_describes_real_bertscore() -> None:
    result = SimpleNamespace(
        id="run-1",
        summary={
            "total_cases": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "pass_rate": 1.0,
            "flows": {"assistant_rag": {"passed": 1, "total": 1}},
        },
        case_results=[],
    )

    report = render_markdown_report(result)

    assert "model-backed BERTScore" in report
    assert "token F1" not in report
    assert "dependency-free" not in report
    assert "BERTScore-compatible" not in report


@pytest.mark.asyncio
async def test_runner_persists_results_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner_module,
        "bertscore",
        lambda reference, candidate: {"precision": 1.0, "recall": 1.0, "f1": 1.0},
    )

    result = await EvaluationRunner(output_dir=tmp_path).run()

    assert result.summary["total_cases"] == 50
    assert result.summary["failed_cases"] == 0
    assert result.summary["visual_metrics"]["top_1_accuracy"] == 1
    assert result.report_path is not None
    assert Path(result.report_path).exists()
    assert (tmp_path / result.id / "result.json").exists()
    assert "Evaluation Report" in Path(result.report_path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_runner_records_failed_judge_result(tmp_path: Path) -> None:
    case = EvaluationCase(
        id="judge-failure-case",
        flow="assistant_rag",
        input={"prompt": "How should I care for this plant?"},
    )

    result = await EvaluationRunner(
        judge_provider=FailingJudgeProvider(),
        output_dir=tmp_path,
    ).run(cases=[case])

    case_result = result.case_results[0]
    assert case_result.passed is False
    assert case_result.failures == ["Grounding criterion failed."]

    persisted = json.loads((tmp_path / result.id / "result.json").read_text(encoding="utf-8"))
    persisted_case = persisted["case_results"][0]
    assert persisted_case["passed"] is False
    assert persisted_case["failures"] == ["Grounding criterion failed."]


@pytest.mark.asyncio
async def test_runner_records_failed_tool_action_claim(tmp_path: Path) -> None:
    case = EvaluationCase(
        id="failed-tool-claim-case",
        flow="reminders_agent",
        input={"prompt": "Create a watering reminder."},
        tool_trace=[
            ToolTrace(
                name="create_reminder",
                success=False,
                claimed_success=True,
            ),
        ],
    )

    result = await EvaluationRunner(output_dir=tmp_path).run(cases=[case])

    case_result = result.case_results[0]
    assert case_result.passed is False
    assert case_result.scores["failed_action_claim_rate"] > 0
    assert "failed tool action was claimed as completed" in case_result.failures
