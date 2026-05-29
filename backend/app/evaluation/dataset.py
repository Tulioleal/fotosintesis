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


class RetrievedDocument(BaseModel):
    id: str
    text: str
    score: float = 1.0


class ToolTrace(BaseModel):
    name: str
    expected: bool = True
    called: bool = True
    success: bool = True
    claimed_success: bool = True


class VisualCandidate(BaseModel):
    scientific_name: str
    confidence: float | None = None
    confidence_label: str | None = None
    taxonomy_validated: bool = False


class EvaluationCase(BaseModel):
    id: str
    flow: EvaluationFlow
    input: dict[str, Any]
    reference_output: str | None = None
    expected_relevant_document_ids: list[str] = Field(default_factory=list)
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    expected_scientific_name: str | None = None
    expected_low_confidence: bool = False
    visual_candidates: list[VisualCandidate] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


SEED_DATASET_PATH = Path(__file__).with_name("data") / "seed_cases.json"


def load_seed_cases(path: Path = SEED_DATASET_PATH) -> list[EvaluationCase]:
    with path.open(encoding="utf-8") as dataset_file:
        data = json.load(dataset_file)
    return [EvaluationCase.model_validate(item) for item in data["cases"]]
