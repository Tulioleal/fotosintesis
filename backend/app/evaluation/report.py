from typing import Protocol


class ReportableRun(Protocol):
    id: str
    mode: str
    recording_version: int | None
    profile: str
    summary: dict
    case_results: list


def render_markdown_report(result: ReportableRun) -> str:
    cases = result.case_results
    quality_failures = [c for c in cases if c.status == "quality_failure"]
    execution_errors = [c for c in cases if c.status == "execution_error"]
    metric_errors = [c for c in cases if c.status == "metric_error"]
    unsupported = [c for c in cases if c.status == "unsupported"]
    summary = result.summary

    lines = [
        "# Evaluation Report",
        "",
        "## Run",
        f"- Run ID: {result.id}",
        f"- Mode: {result.mode}",
        f"- Recording version: {result.recording_version if result.recording_version is not None else 'n/a'}",
        f"- Threshold profile: {result.profile}",
        "",
        "## Protocol",
        "Every run case is executed through the current assistant graph. Observed responses, "
        "retrieval evidence, tool outcomes, and validation state are read from the resulting graph "
        "state and are never populated from reference output or expected fixtures.",
        "",
        "## Metrics",
        "- retrieval_recall@5 and precision@5 from observed retrieval evidence",
        "- model-backed BERTScore and ROUGE-L for referenced text outputs",
        "- LLM-as-a-judge rubric scores for grounding, botanical correctness, usefulness, clarity, "
        "safety, uncertainty handling and tool use",
        "- tool_success_rate and tool_assertion_satisfaction from observed tool records",
        "",
        "## Results",
        f"- Total cases: {summary.get('total_cases', 0)}",
        f"- Passed: {summary.get('passed_cases', 0)}",
        f"- Quality failures: {summary.get('quality_failures', 0)}",
        f"- Execution errors: {summary.get('execution_errors', 0)}",
        f"- Metric errors: {summary.get('metric_errors', 0)}",
        f"- Unsupported: {summary.get('unsupported', 0)}",
        f"- Pass rate (scored cases): {summary.get('pass_rate', 0):.2%}",
        f"- Aggregate approved: {summary.get('aggregate_approved', False)}",
        "",
        "## Per-Flow Summary",
    ]
    for flow, per_flow in sorted(summary.get("flows", {}).items()):
        lines.append(
            f"- {flow}: {per_flow.get('passed', 0)}/{per_flow.get('total', 0)} passed; "
            f"{per_flow.get('execution_error', 0)} execution errors, "
            f"{per_flow.get('metric_error', 0)} metric errors, "
            f"{per_flow.get('quality_failure', 0)} quality failures, "
            f"{per_flow.get('unsupported', 0)} unsupported"
        )

    lines.extend(["", "## Quality Failures"])
    if quality_failures:
        for case in quality_failures:
            lines.append(f"- {case.case_id}: {'; '.join(case.failures)}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Execution Errors"])
    if execution_errors:
        for case in execution_errors:
            detail = case.error_detail or ""
            lines.append(f"- {case.case_id}: {case.error_category or 'error'} - {detail}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Metric Errors"])
    if metric_errors:
        for case in metric_errors:
            detail = case.error_detail or ""
            lines.append(f"- {case.case_id}: {detail}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Unsupported Cases"])
    if unsupported:
        for case in unsupported:
            lines.append(f"- {case.case_id}: {case.skip_reason or 'unsupported'}")
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Limitations",
            "Automatic metrics do not prove botanical correctness. Live mode is non-deterministic. "
            "BERTScore provides model-backed semantic similarity for referenced text outputs and "
            "depends on the configured model assets.",
            "",
            "## Conclusions",
            "Use failed cases, execution errors, and low per-flow pass rates to prioritize regression "
            "fixes and dataset expansion.",
            "",
        ]
    )
    return "\n".join(lines)
