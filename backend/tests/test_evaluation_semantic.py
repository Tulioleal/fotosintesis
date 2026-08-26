from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation.dataset import EvaluationCase
from app.evaluation.runner import EvaluationRunner

from tests._evaluation_helpers import mock_registry, patch_bertscore


@pytest.mark.asyncio
async def test_non_english_paraphrased_evidence_reaches_retrieval_and_judging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A paraphrased / non-English knowledge document is retrieved by semantic
    (identifier-based) retrieval and reaches the semantic judge, without any
    keyword match on the expected relevance label."""
    patch_bertscore(monkeypatch)

    case = EvaluationCase(
        id="semantic_rag_es",
        flow="assistant_rag",
        input={"prompt": "¿Por qué se ponen amarillas las hojas de mi monstera?"},
        setup={
            "plant_binomial_name": "Monstera deliciosa",
            "plant_hint": "monstera",
            "knowledge": [
                {
                    "scientific_name": "Monstera deliciosa",
                    "topic": "watering",
                    "source_url": "https://example.org/monstera_hojas_amarillas",
                    "content": (
                        "El amarillamiento de las hojas de la monstera se asocia "
                        "a un exceso de riego o a un drenaje deficiente."
                    ),
                }
            ],
        },
        expected_relevant_document_ids=["monstera_hojas_amarillas"],
        reference_output="Amarillamiento asociado a exceso de riego o mal drenaje.",
    )

    result = await EvaluationRunner(
        output_dir=tmp_path, base_registry=mock_registry()
    ).run(cases=[case])

    observed = result.case_results[0]
    # The evidence is retrieved by its stable identifier, not by matching the
    # English label text via keywords.
    assert "monstera_hojas_amarillas" in observed.retrieved_evidence_ids
    # Retrieval recall from observed (not keyword) data is complete.
    assert observed.scores.get("retrieval_recall@5") == 1.0
    # The case reaches the semantic judge with graph-produced output.
    assert observed.judge is not None
    assert observed.output
    assert observed.answer_language is not None
