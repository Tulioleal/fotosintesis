"""Snapshot test that fails when the generated OpenAPI schema drifts.

Mirrors ``scripts/check_openapi_diff.py`` so the same check runs in
``pytest`` (which the rest of the architecture/layering/file-size checks
also rely on) and in standalone CI scripts. The baseline is captured at
the end of the ``backend-dead-code-architecture-refactor`` change, which
is supposed to be behavior-preserving.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

BASELINE_PATH = ROOT / "openapi-baseline.json"


def test_openapi_schema_matches_baseline() -> None:
    assert BASELINE_PATH.exists(), (
        f"OpenAPI baseline missing at {BASELINE_PATH}. "
        "Run `python3 scripts/check_openapi_diff.py --update` to create it."
    )
    current_text = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    baseline_text = BASELINE_PATH.read_text(encoding="utf-8")
    assert current_text == baseline_text, (
        "OpenAPI schema drift detected. Run "
        "`python3 scripts/check_openapi_diff.py --update` if the change is intentional."
    )
