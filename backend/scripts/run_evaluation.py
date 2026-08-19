import argparse
import asyncio
from pathlib import Path

from app.evaluation import EvaluationRunner
from app.core.settings import get_settings


async def main() -> None:
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
        "--output",
        type=Path,
        default=Path("evaluation-runs"),
        help="Output directory for reports.",
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
    ).run()
    print(f"Evaluation run {result.id} complete ({mode}): {result.report_path}")


if __name__ == "__main__":
    asyncio.run(main())
