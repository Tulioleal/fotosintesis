from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.evaluation.dataset import EvaluationCase
from app.evaluation.runner import EvaluationRunner
from app.providers.mocks import MockModelProvider
from app.providers.types import JsonGenerationResult, TextGenerationResult

from tests._evaluation_helpers import executable_cases, mock_registry, patch_bertscore


class CustomTextModelProvider(MockModelProvider):
    def __init__(self, *, text: str) -> None:
        super().__init__()
        self._text = text

    async def generate_text(self, prompt: str, **kwargs: Any) -> TextGenerationResult:
        return TextGenerationResult(
            provider="custom-text",
            model="custom",
            text=self._text,
        )

    async def generate_json(
        self, prompt: str, schema: dict[str, Any], **kwargs: Any
    ) -> JsonGenerationResult:
        return await super().generate_json(prompt, schema, **kwargs)


@pytest.mark.asyncio
async def test_observed_output_changes_when_assistant_behavior_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    cases = executable_cases()

    runner_a = EvaluationRunner(
        output_dir=tmp_path / "a",
        base_registry=mock_registry(model=CustomTextModelProvider(text="Alpha answer")),
    )
    runner_b = EvaluationRunner(
        output_dir=tmp_path / "b",
        base_registry=mock_registry(model=CustomTextModelProvider(text="Beta answer")),
    )

    result_a = await runner_a.run(cases=cases)
    result_b = await runner_b.run(cases=cases)

    outputs_a = {c.case_id: c.output for c in result_a.case_results}
    outputs_b = {c.case_id: c.output for c in result_b.case_results}
    executable_ids = {c.id for c in cases}
    assert any(outputs_a[case_id] != outputs_b[case_id] for case_id in executable_ids)


@pytest.mark.asyncio
async def test_reference_text_is_never_returned_as_candidate_without_graph_production(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    cases = executable_cases()
    referenced = [case for case in cases if case.reference_output]

    result = await EvaluationRunner(output_dir=tmp_path).run(cases=cases)

    for case in referenced:
        observed = next(c for c in result.case_results if c.case_id == case.id)
        # The observed output must not equal the reference text unless the
        # graph actually produced that exact text (it does not with the mock
        # provider, which returns a deterministic placeholder).
        assert observed.output != case.reference_output


@pytest.mark.asyncio
async def test_unsupported_case_is_reconciled_and_not_scored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    case = EvaluationCase(
        id="unsupported-flow",
        flow="revive_plant",
        input={"prompt": "Revive a pothos"},
    )
    result = await EvaluationRunner(output_dir=tmp_path).run(cases=[case])
    assert result.case_results[0].status == "unsupported"
    assert result.case_results[0].skip_reason is not None


@pytest.mark.asyncio
async def test_execution_error_is_classified_separately_from_quality_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)

    case = executable_cases()[0]
    runner = EvaluationRunner(output_dir=tmp_path, base_registry=mock_registry())

    async def failing_build_graph(session, registry, runtime):
        raise RuntimeError("graph construction failed")

    monkeypatch.setattr(runner, "_build_graph", failing_build_graph)

    result = await runner.run(cases=[case])

    assert result.case_results[0].status == "execution_error"
    assert result.case_results[0].error_category is not None


@pytest.mark.asyncio
async def test_cases_are_isolated_from_each_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    cases = executable_cases()

    result = await EvaluationRunner(output_dir=tmp_path).run(cases=cases)

    by_id = {c.case_id: c for c in result.case_results}
    # assistant_rag_01 seeds two knowledge docs and retrieves both expected ids.
    rag01 = by_id["assistant_rag_01"]
    assert "monstera_watering" in rag01.retrieved_evidence_ids
    assert "monstera_light" in rag01.retrieved_evidence_ids
    # assistant_rag_02 seeds only snake-plant knowledge and must not inherit
    # Monstera evidence from the previous case.
    rag02 = by_id["assistant_rag_02"]
    assert "monstera_watering" not in rag02.retrieved_evidence_ids
    assert "sansevieria_watering" in rag02.retrieved_evidence_ids


@pytest.mark.asyncio
async def test_reference_mode_is_non_passing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_bertscore(monkeypatch)
    case = executable_cases()[0]
    result = await EvaluationRunner(output_dir=tmp_path, mode="reference").run(cases=[case])
    assert result.case_results[0].status == "quality_failure"
    assert "non-passing" in (result.case_results[0].failures or [])[0]
