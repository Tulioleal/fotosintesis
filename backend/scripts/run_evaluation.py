import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.evaluation import EvaluationRunner
from app.core.settings import get_settings
from app.evaluation.metrics import (
    DEFAULT_EVALUATION_PROFILE,
    QUALITY_GATE_PROFILE,
    EvaluationProfile,
)


def mock_registry():
    """Deterministic provider set matching the committed CI recording."""
    from app.providers.factory import ProviderRegistry
    from app.providers.mocks import (
        MockEmbeddingProvider,
        MockModelProvider,
        MockPerenualPlantDataProvider,
        MockSearchProvider,
        MockTreflePlantDataProvider,
        MockVisionPlantIdentificationProvider,
    )

    return ProviderRegistry(
        model=MockModelProvider(),
        vision=MockVisionPlantIdentificationProvider(),
        judge=MockModelProvider(),
        search=MockSearchProvider(),
        embeddings=MockEmbeddingProvider(),
        trefle=MockTreflePlantDataProvider(),
        perenual=MockPerenualPlantDataProvider(),
    )


PROFILES: dict[str, EvaluationProfile] = {
    "quality_gate": QUALITY_GATE_PROFILE,
    "default": DEFAULT_EVALUATION_PROFILE,
}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the assistant evaluation.")
    parser.add_argument(
        "--mode",
        choices=["recorded", "live", "reference"],
        default=None,
        help="Evaluation mode (default: settings.evaluation_mode or 'recorded').",
    )
    parser.add_argument(
        "--recording",
        type=Path,
        default=None,
        help="Path to the provider recording set for recorded/replay mode.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="quality_gate",
        help="Threshold profile enforcing the run approval gate.",
    )
    parser.add_argument(
        "--providers",
        choices=["settings", "mock"],
        default="mock",
        help="Provider set: 'mock' replays the committed deterministic recording; "
        "'settings' builds the configured live registry.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation-runs"),
        help="Output directory for reports (retention bounded by settings).",
    )
    args = parser.parse_args()

    settings = get_settings()
    mode = args.mode or settings.evaluation_mode
    recording = args.recording or (
        Path(settings.evaluation_recording_path)
        if settings.evaluation_recording_path
        else None
    )

    result = await EvaluationRunner(
        output_dir=args.output,
        mode=mode,
        recording_path=recording,
        profile=PROFILES[args.profile],
        base_registry=mock_registry() if args.providers == "mock" else None,
    ).run()

    summary = result.summary
    gate = summary.get("gate", {})
    print(f"Evaluation run {result.id} complete ({mode}, profile {args.profile}).")
    print(
        json.dumps(
            {
                "approved": gate.get("approved", False),
                "coverage_failure": gate.get("coverage_failure", False),
                "supported_case_ratio": round(gate.get("supported_case_ratio", 0.0), 4),
                "pass_rate": round(summary.get("pass_rate", 0.0), 4),
                "passed": summary.get("passed_cases", 0),
                "quality_failures": summary.get("quality_failures", 0),
                "execution_errors": summary.get("execution_errors", 0),
                "metric_errors": summary.get("metric_errors", 0),
                "unsupported": summary.get("unsupported", 0),
                "reasons": gate.get("reasons", []),
            },
            indent=2,
        )
    )
    print(f"Report: {result.report_path}")

    if not gate.get("approved", False):
        print("Quality gate NOT approved.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
