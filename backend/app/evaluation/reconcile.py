"""Load-time reconciliation of evaluation cases against the graph's tools.

Cases whose expected tools or flows are absent from the current graph are
marked unsupported with an explicit reason. They are never scored as if their
expected behavior had occurred.
"""

from __future__ import annotations

from app.evaluation.dataset import EvaluationCase

# Tools exposed by the AssistantTools facade that the graph can actually drive.
GRAPH_TOOL_CAPABILITIES: frozenset[str] = frozenset(
    {
        "knowledge_search",
        "trusted_web_search",
        "generate_text",
        "generate_json",
        "plant_data_lookup",
        "garden_lookup",
        "reminder_create",
        "light_measurement_lookup",
    }
)

# Seed flows that the current graph does not implement as distinct flows.
UNSUPPORTED_FLOWS: frozenset[str] = frozenset(
    {
        "plant_profile_generation",
        "revive_plant",
        "incremental_knowledge",
        "plant_identification_maas",
    }
)

# Historical tool-trace names that do not map to a graph capability.
_UNSUPPORTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "care_plan",
        "cancel_reminder",
        "list_reminders",
        "update_reminder",
        "read_light_measurement",
    }
)

_ALIASES: dict[str, str] = {
    "web_search": "trusted_web_search",
    "create_reminder": "reminder_create",
}


def reconcile_case(case: EvaluationCase) -> EvaluationCase:
    """Return a copy of ``case`` marked unsupported when its flow or expected
    tools are absent from the current graph."""
    if case.unsupported:
        return case
    reasons: list[str] = []

    if case.flow in UNSUPPORTED_FLOWS:
        reasons.append(f"flow '{case.flow}' is not implemented as a distinct graph flow")

    for assertion in case.tool_assertions:
        if not assertion.expected:
            continue
        capability = _ALIASES.get(assertion.name, assertion.name)
        if capability not in GRAPH_TOOL_CAPABILITIES:
            reasons.append(
                f"expected tool '{assertion.name}' is absent from the graph tool set"
            )
        elif assertion.name in _UNSUPPORTED_TOOL_NAMES:
            reasons.append(
                f"expected tool '{assertion.name}' is not driven by the graph"
            )

    if not reasons:
        return case
    return case.model_copy(
        update={"unsupported": True, "skip_reason": "; ".join(reasons)}
    )


def reconcile_cases(cases: list[EvaluationCase]) -> list[EvaluationCase]:
    return [reconcile_case(case) for case in cases]


__all__ = [
    "GRAPH_TOOL_CAPABILITIES",
    "UNSUPPORTED_FLOWS",
    "reconcile_case",
    "reconcile_cases",
]
