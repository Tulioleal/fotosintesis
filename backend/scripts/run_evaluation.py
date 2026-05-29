import asyncio
from pathlib import Path

from app.evaluation import EvaluationRunner


async def main() -> None:
    result = await EvaluationRunner(output_dir=Path("evaluation-runs")).run()
    print(f"Evaluation run {result.id} complete: {result.report_path}")


if __name__ == "__main__":
    asyncio.run(main())
