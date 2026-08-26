from pathlib import Path
from typing import Any, Literal
import json

from pydantic import BaseModel, Field


EvaluationFlow = Literal[
    "assistant_rag",
    "plant_profile_generation",
    "revive_plant",
    "incremental_knowledge",
    "reminders_agent",
    "light_measurement_context",
    "plant_identification_maas",
]


class ToolAssertion(BaseModel):
    """Expected tool behavior expressed as an assertion, not an observed trace."""

    name: str
    expected: bool = True
    expected_success: bool = True


class VisualCandidate(BaseModel):
    scientific_name: str
    confidence: float | None = None
    confidence_label: str | None = None
    taxonomy_validated: bool = False


class EvaluationCase(BaseModel):
    """A dataset case.

    Expected/reference fields (``reference_output``, expected relevant
    document ids, tool assertions, visual candidates) are kept separate from
    observed execution records. The runner never copies these into the
    observed result; observed data always comes from the executed graph.
    """

    id: str
    flow: EvaluationFlow
    input: dict[str, Any]
    setup: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-case fixture state used to isolate and seed the run (user, garden, knowledge).",
    )
    reference_output: str | None = None
    expected_relevant_document_ids: list[str] = Field(default_factory=list)
    tool_assertions: list[ToolAssertion] = Field(default_factory=list)
    expected_scientific_name: str | None = None
    expected_low_confidence: bool = False
    visual_candidates: list[VisualCandidate] = Field(default_factory=list)
    unsupported: bool = False
    skip_reason: str | None = None
    tags: list[str] = Field(default_factory=list)


SEED_DATASET_PATH = Path(__file__).with_name("data") / "seed_cases.json"


def load_seed_cases(path: Path = SEED_DATASET_PATH) -> list[EvaluationCase]:
    with path.open(encoding="utf-8") as dataset_file:
        data = json.load(dataset_file)
    return [EvaluationCase.model_validate(item) for item in data["cases"]]
