#!/usr/bin/env python3
"""Fail CI when the generated OpenAPI schema drifts from the checked-in baseline.

The baseline is captured at the end of the
``backend-dead-code-architecture-refactor`` change, which is supposed to be
behavior-preserving. Any drift in a follow-up change indicates an unintended
HTTP API surface change and must be reviewed.

Usage::

    # CI: compare against the baseline and exit non-zero on drift
    python3 scripts/check_openapi_diff.py

    # Intentional API change: regenerate the baseline after review
    python3 scripts/check_openapi_diff.py --update

    # Same checks wrapped as a pytest test (see tests/test_openapi_snapshot.py)
    pytest -x tests/test_openapi_snapshot.py
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

BASELINE_PATH = ROOT / "openapi-baseline.json"


def current_openapi() -> dict:
    """Return the OpenAPI schema produced by the running app, normalized."""
    return normalize_openapi(app.openapi())


def normalize_openapi(schema: dict) -> dict:
    """Remove OpenAPI generator noise that varies across dependency versions."""
    normalized = json.loads(json.dumps(schema))

    validation_error = normalized.get("components", {}).get("schemas", {}).get("ValidationError")
    if isinstance(validation_error, dict):
        properties = validation_error.get("properties")
        if isinstance(properties, dict):
            properties.pop("ctx", None)
            properties.pop("input", None)

    _normalize_file_upload_schema(normalized)
    return normalized


def _normalize_file_upload_schema(value: object) -> None:
    if isinstance(value, dict):
        if value.get("type") == "string" and value.get("contentMediaType") == "application/octet-stream":
            value.pop("contentMediaType", None)
            value.setdefault("format", "binary")
        for item in value.values():
            _normalize_file_upload_schema(item)
    elif isinstance(value, list):
        for item in value:
            _normalize_file_upload_schema(item)


def render_openapi(schema: dict) -> str:
    """Render the schema as a stable text representation for diffing."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def diff_summaries(current: dict, baseline: dict) -> str:
    """Return a human-readable summary of the top-level diffs."""
    current_paths = set(current.get("paths", {}).keys())
    baseline_paths = set(baseline.get("paths", {}).keys())
    added_paths = sorted(current_paths - baseline_paths)
    removed_paths = sorted(baseline_paths - current_paths)
    current_schemas = set(current.get("components", {}).get("schemas", {}).keys())
    baseline_schemas = set(baseline.get("components", {}).get("schemas", {}).keys())
    added_schemas = sorted(current_schemas - baseline_schemas)
    removed_schemas = sorted(baseline_schemas - current_schemas)
    parts: list[str] = []
    if added_paths:
        parts.append(f"  + paths: {', '.join(added_paths)}")
    if removed_paths:
        parts.append(f"  - paths: {', '.join(removed_paths)}")
    if added_schemas:
        parts.append(f"  + schemas: {', '.join(added_schemas)}")
    if removed_schemas:
        parts.append(f"  - schemas: {', '.join(removed_schemas)}")
    return "\n".join(parts) if parts else "  (no top-level path or schema additions/removals)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the generated OpenAPI schema against the checked-in baseline."
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate the baseline from the current schema and exit 0.",
    )
    args = parser.parse_args()

    current = current_openapi()
    current_text = render_openapi(current)

    if args.update or not BASELINE_PATH.exists():
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(current_text, encoding="utf-8")
        action = "updated" if BASELINE_PATH.exists() else "created"
        print(f"OpenAPI baseline {action} at {BASELINE_PATH.relative_to(ROOT)}")
        return 0

    baseline_text = BASELINE_PATH.read_text(encoding="utf-8")
    if current_text == baseline_text:
        print("OpenAPI schema matches baseline.")
        return 0

    baseline = json.loads(baseline_text)
    print("OpenAPI schema drift detected:")
    print(diff_summaries(current, baseline))
    print()
    diff = difflib.unified_diff(
        baseline_text.splitlines(keepends=True),
        current_text.splitlines(keepends=True),
        fromfile=f"baseline:{BASELINE_PATH.name}",
        tofile="current:app.openapi()",
        n=3,
    )
    for line in diff:
        print(line, end="")
    print()
    print("If the drift is intentional, run `python3 scripts/check_openapi_diff.py --update`.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
