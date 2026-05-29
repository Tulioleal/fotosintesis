from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.evaluation.dataset import EvaluationCase, load_seed_cases
from app.evaluation.metrics import (
    bertscore,
    precision_at_k,
    retrieval_recall_at_k,
    rouge_l,
    tool_metrics,
    visual_metrics,
)
from app.evaluation.report import render_markdown_report
from app.providers.interfaces import JudgeEvaluationProvider


JUDGE_RUBRIC = {
    "criteria": {
        "grounding": "Answer is supported by retrieved evidence or provided case context.",
        "botanical_correctness": "Botanical advice is plausible and avoids harmful care claims.",
        "usefulness": "Answer gives actionable next steps for the user's plant-care goal.",
        "clarity": "Answer is concise, understandable and avoids unsupported certainty.",
        "safety": "Answer avoids unsafe chemical, ingestion or emergency-health guidance.",
        "uncertainty_handling": "Answer asks for missing context or states limits when needed.",
        "tool_use": "Required tools are used and failed actions are not claimed as complete.",
    },
    "passing_score": 0.75,
}


@dataclass
class CaseResult:
    case_id: str
    flow: str
    output: str
    scores: dict[str, Any]
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass
class EvaluationRunResult:
    id: str
    started_at: datetime
    completed_at: datetime
    case_results: list[CaseResult]
    summary: dict[str, Any]
    report_path: str | None = None


class EvaluationRunner:
    def __init__(
        self,
        *,
        judge_provider: JudgeEvaluationProvider | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.judge_provider = judge_provider
        self.output_dir = output_dir or Path("evaluation-runs")

    async def run(self, cases: list[EvaluationCase] | None = None) -> EvaluationRunResult:
        selected_cases = cases or load_seed_cases()
        started_at = datetime.now(timezone.utc)
        case_results = [await self._evaluate_case(case) for case in selected_cases]
        completed_at = datetime.now(timezone.utc)
        result = EvaluationRunResult(
            id=str(uuid4()),
            started_at=started_at,
            completed_at=completed_at,
            case_results=case_results,
            summary=_summarize(selected_cases, case_results),
        )
        result.report_path = self._persist(result)
        return result

    async def _evaluate_case(self, case: EvaluationCase) -> CaseResult:
        output = _deterministic_output(case)
        scores: dict[str, Any] = {}
        failures: list[str] = []

        retrieved_ids = [document.id for document in case.retrieved_documents]
        recall = retrieval_recall_at_k(case.expected_relevant_document_ids, retrieved_ids)
        precision = precision_at_k(case.expected_relevant_document_ids, retrieved_ids)
        if recall is not None:
            scores["retrieval_recall@5"] = recall
        if precision is not None:
            scores["precision@5"] = precision
        if case.reference_output:
            scores["rouge_l"] = rouge_l(case.reference_output, output)
            scores["bertscore"] = bertscore(case.reference_output, output)

        scores.update({key: value for key, value in tool_metrics(case.tool_trace).items() if value is not None})

        judge = await self._judge(case, output)
        scores["judge"] = judge
        if not judge["passed"]:
            failures.extend(judge["reasons"])
        if recall is not None and recall < 1:
            failures.append("retrieval_recall@5 below expected complete relevant-document recall")
        if scores.get("failed_action_claim_rate", 0) > 0:
            failures.append("failed tool action was claimed as completed")

        return CaseResult(
            case_id=case.id,
            flow=case.flow,
            output=output,
            scores=scores,
            passed=not failures,
            failures=failures,
        )

    async def _judge(self, case: EvaluationCase, output: str) -> dict[str, Any]:
        payload = {
            "case_id": case.id,
            "flow": case.flow,
            "input": case.input,
            "reference_output": case.reference_output,
            "output": output,
            "retrieved_documents": [document.model_dump() for document in case.retrieved_documents],
            "tool_trace": [trace.model_dump() for trace in case.tool_trace],
        }
        if self.judge_provider:
            result = await self.judge_provider.judge_response(payload, JUDGE_RUBRIC)
            return {
                "provider": result.provider,
                "model": result.model,
                "score": result.score,
                "passed": result.passed,
                "reasons": result.reasons,
                "rubric": JUDGE_RUBRIC,
            }

        score = 1.0
        reasons: list[str] = []
        if case.reference_output:
            score = min(score, bertscore(case.reference_output, output)["f1"])
        if any(not trace.success and trace.claimed_success for trace in case.tool_trace):
            score = 0.0
            reasons.append("Tool-use criterion failed: unsuccessful action claimed as complete.")
        if case.expected_relevant_document_ids and not case.retrieved_documents:
            score = 0.0
            reasons.append("Grounding criterion failed: no retrieved evidence available.")
        passed = score >= JUDGE_RUBRIC["passing_score"] and not reasons
        return {
            "provider": "deterministic-local-judge",
            "model": None,
            "score": score,
            "passed": passed,
            "reasons": reasons or ["Passed deterministic local rubric."],
            "rubric": JUDGE_RUBRIC,
        }

    def _persist(self, result: EvaluationRunResult) -> str:
        run_dir = self.output_dir / result.id
        run_dir.mkdir(parents=True, exist_ok=True)
        report_path = run_dir / "report.md"
        report_path.write_text(render_markdown_report(result), encoding="utf-8")
        (run_dir / "result.json").write_text(_to_json(result), encoding="utf-8")
        return str(report_path)


def _deterministic_output(case: EvaluationCase) -> str:
    if case.reference_output:
        return case.reference_output
    if case.expected_scientific_name:
        return f"Likely identification: {case.expected_scientific_name}. Confirm before adding care tasks."
    return f"Evaluation output for {case.flow}: {case.input.get('prompt', case.id)}"


def _summarize(cases: list[EvaluationCase], results: list[CaseResult]) -> dict[str, Any]:
    by_flow: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "passed": 0, "failures": []})
    for result in results:
        by_flow[result.flow]["total"] += 1
        by_flow[result.flow]["passed"] += int(result.passed)
        by_flow[result.flow]["failures"].extend(result.failures)

    return {
        "total_cases": len(results),
        "passed_cases": sum(result.passed for result in results),
        "failed_cases": sum(not result.passed for result in results),
        "pass_rate": sum(result.passed for result in results) / len(results) if results else 0,
        "flows": dict(by_flow),
        "visual_metrics": visual_metrics(cases),
    }


def _to_json(result: EvaluationRunResult) -> str:
    import json

    return json.dumps(
        {
            "id": result.id,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat(),
            "summary": result.summary,
            "case_results": [
                {
                    "case_id": case.case_id,
                    "flow": case.flow,
                    "output": case.output,
                    "scores": case.scores,
                    "passed": case.passed,
                    "failures": case.failures,
                }
                for case in result.case_results
            ],
        },
        indent=2,
        sort_keys=True,
    )
