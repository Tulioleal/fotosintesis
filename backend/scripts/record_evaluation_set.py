"""Record a committed CI evaluation recording set.

Uses the deterministic mock provider set (the same providers CI runs with) so
the recording is self-contained and reproducible without any live provider.
Writes the versioned JSON recording set that recorded-mode CI runs replay.
"""

import argparse
import asyncio
from pathlib import Path

from app.evaluation import EvaluationRunner
from app.evaluation.dataset import load_seed_cases
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


def mock_registry() -> ProviderRegistry:
    return ProviderRegistry(
        model=MockModelProvider(),
        vision=MockVisionPlantIdentificationProvider(),
        judge=MockModelProvider(),
        search=MockSearchProvider(),
        embeddings=MockEmbeddingProvider(),
        trefle=MockTreflePlantDataProvider(),
        perenual=MockPerenualPlantDataProvider(),
    )


DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "app" / "evaluation" / "data" / "recordings" / "ci-recording.json"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Record the committed CI evaluation recording set.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tmp", type=Path, default=Path("evaluation-runs-record"))
    args = parser.parse_args()

    cases = reconcile_cases(load_seed_cases())
    run = await EvaluationRunner(
        output_dir=args.tmp,
        mode="record",
        recording_path=args.output,
        base_registry=mock_registry(),
    ).run(cases=cases)

    print(f"Recorded {args.output}")
    print(f"Entries recorded; cases executed={run.summary['total_cases']}")


if __name__ == "__main__":
    asyncio.run(main())
