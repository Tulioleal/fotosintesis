from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation.runner import EvaluationRunner

from tests._evaluation_helpers import executable_cases, patch_bertscore

CI_RECORDING = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "evaluation"
    / "data"
    / "recordings"
    / "ci-recording.json"
)


@pytest.mark.asyncio
async def test_record_then_replay_is_reproducible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    cases = executable_cases()
    recording = tmp_path / "recording.json"

    recorded = await EvaluationRunner(
        output_dir=tmp_path / "record",
        mode="record",
        recording_path=recording,
    ).run(cases=cases)

    assert recording.exists()
    assert recorded.recording_version == 1

    replay_a = await EvaluationRunner(
        output_dir=tmp_path / "replay-a",
        mode="recorded",
        recording_path=recording,
    ).run(cases=cases)

    replay_b = await EvaluationRunner(
        output_dir=tmp_path / "replay-b",
        mode="recorded",
        recording_path=recording,
    ).run(cases=cases)

    def key(r):
        return {(c.case_id, c.status, c.output, tuple(c.retrieved_evidence_ids)) for c in r.case_results}

    assert key(replay_a) == key(replay_b)
    assert key(recorded) == key(replay_a)
    assert replay_a.recording_version == 1


@pytest.mark.asyncio
async def test_missing_recording_fails_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_bertscore(monkeypatch)
    cases = executable_cases()[:1]
    runner = EvaluationRunner(
        output_dir=tmp_path,
        mode="recorded",
        recording_path=tmp_path / "missing.json",
    )
    with pytest.raises(Exception):
        await runner.run(cases=cases)


@pytest.mark.asyncio
async def test_committed_ci_recording_replays_reproducibly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed CI recording set replays deterministically across runs."""
    if not CI_RECORDING.exists():
        pytest.skip("CI recording set not present")
    patch_bertscore(monkeypatch)
    cases = executable_cases()

    replay_a = await EvaluationRunner(
        output_dir=tmp_path / "a",
        mode="recorded",
        recording_path=CI_RECORDING,
    ).run(cases=cases)

    replay_b = await EvaluationRunner(
        output_dir=tmp_path / "b",
        mode="recorded",
        recording_path=CI_RECORDING,
    ).run(cases=cases)

    def key(r):
        return {(c.case_id, c.status, c.output, tuple(c.retrieved_evidence_ids)) for c in r.case_results}

    assert key(replay_a) == key(replay_b)
    assert replay_a.recording_version == 1
