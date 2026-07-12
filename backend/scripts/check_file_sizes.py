#!/usr/bin/env python3
"""Enforce backend file-size hard caps.

Fails CI when any backend source file or test file exceeds the
configured hard cap. Provider adapter modules, service modules, slice
internals, graph node modules, prompt modules, and test files are
each compared against their own limit.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path("app")
TESTS_DIR = Path("tests")

CAPS: dict[str, int] = {
    "provider_adapter": 500,
    "service": 500,
    "slice_internal": 500,
    "graph_module": 500,
    "prompt_module": 500,
    "test_file": 1000,
    "default": 500,
}


def classify(path: Path) -> str:
    rel = path.as_posix()
    if rel.startswith("app/providers/") and rel.endswith(".py"):
        if "/openai/" in rel or "/gemini/" in rel or "/wrappers/" in rel:
            return "provider_adapter"
        return "provider_adapter"
    if rel.startswith("tests/") and rel.endswith(".py"):
        return "test_file"
    if rel.startswith("app/assistant/graph/"):
        return "graph_module"
    if rel.startswith("app/assistant/prompts/") or "/prompts/" in rel:
        return "prompt_module"
    if "/service" in rel and rel.endswith(".py"):
        return "service"
    return "default"


def main() -> int:
    failures: list[str] = []
    for root in (APP_DIR, TESTS_DIR):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.name == "__init__.py" and path.parent == root:
                continue
            try:
                line_count = sum(1 for _ in path.open("rb"))
            except OSError:
                continue
            category = classify(path)
            cap = CAPS.get(category, CAPS["default"])
            if line_count > cap:
                failures.append(f"{path}: {line_count} lines exceeds {cap} (category={category})")
    if failures:
        print("File-size hard cap violations:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("All files within size caps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
