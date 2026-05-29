from typing import Protocol


class ReportableRun(Protocol):
    id: str
    summary: dict
    case_results: list


def render_markdown_report(result: ReportableRun) -> str:
    failures = [case for case in result.case_results if not case.passed]
    lines = [
        "# Evaluation Report",
        "",
        "## Protocol",
        "Offline deterministic evaluation over seeded MVP flow cases. Text cases use references, "
        "retrieval cases use expected relevant document IDs, tool cases use captured tool traces, "
        "and visual cases use expected taxonomy candidates.",
        "",
        "## Metrics",
        "- retrieval_recall@5 and precision@5 for retrieval cases",
        "- model-backed BERTScore and ROUGE-L for referenced text outputs",
        "- LLM-as-a-judge rubric scores for grounding, botanical correctness, usefulness, clarity, "
        "safety, uncertainty handling and tool use",
        "- tool_success_rate, unnecessary_web_search_rate and failed_action_claim_rate",
        "- top_1_accuracy, top_3_accuracy, taxonomy_validation_rate and low_confidence_detection_rate",
        "",
        "## Prompts",
        "Prompts are stored per case in the seed dataset input payload and preserved in result.json.",
        "",
        "## Results",
        f"- Run ID: {result.id}",
        f"- Total cases: {result.summary['total_cases']}",
        f"- Passed cases: {result.summary['passed_cases']}",
        f"- Failed cases: {result.summary['failed_cases']}",
        f"- Pass rate: {result.summary['pass_rate']:.2%}",
        "",
        "## Per-Flow Summary",
    ]
    for flow, summary in sorted(result.summary["flows"].items()):
        lines.append(f"- {flow}: {summary['passed']}/{summary['total']} passed")

    lines.extend(["", "## Failures"])
    if failures:
        for case in failures:
            lines.append(f"- {case.case_id}: {'; '.join(case.failures)}")
    else:
        lines.append("- No failures recorded.")

    lines.extend(
        [
            "",
            "## Limitations",
            "Automatic metrics do not prove botanical correctness. BERTScore provides model-backed "
            "semantic similarity for referenced text outputs and depends on the configured model assets.",
            "",
            "## Conclusions",
            "Use failed cases and low per-flow pass rates to prioritize regression fixes and dataset expansion.",
            "",
        ]
    )
    return "\n".join(lines)
