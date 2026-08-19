"""Helpers for evaluation tests."""

from __future__ import annotations

from typing import Any

from app.evaluation import metrics
from app.evaluation.dataset import EvaluationCase, load_seed_cases
from app.evaluation.reconcile import reconcile_cases
from app.providers.factory import ProviderRegistry
from app.providers.mocks import (
    MockEmbeddingProvider,
    MockModelProvider,
    MockPerenualPlantDataProvider,
    MockSearchProvider,
    MockTreflePlantDataProvider,
    MockVisionPlantIdentificationProvider,
)


def patch_bertscore(monkeypatch: Any) -> None:
    def fake_bertscore(candidates: list[str], references: list[str]) -> tuple[list[float], list[float], list[float]]:
        return [0.9], [0.85], [0.87]

    monkeypatch.setattr(metrics, "_run_bert_score", fake_bertscore)


def mock_registry(*, model: Any | None = None) -> ProviderRegistry:
    return ProviderRegistry(
        model=model or MockModelProvider(),
        vision=MockVisionPlantIdentificationProvider(),
        judge=MockModelProvider(),
        search=MockSearchProvider(),
        embeddings=MockEmbeddingProvider(),
        trefle=MockTreflePlantDataProvider(),
        perenual=MockPerenualPlantDataProvider(),
    )


def executable_cases() -> list[EvaluationCase]:
    return [case for case in reconcile_cases(load_seed_cases()) if not case.unsupported]
