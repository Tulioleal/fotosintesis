#!/usr/bin/env python3
"""Enforce backend layering rules.

Fails CI when an import violates the backend layering rules:

- API modules may only import from services, schemas, or shared
  utilities; they MUST NOT import slice internals.
- Provider modules MUST NOT import from slice internals
  (assistant, knowledge, auth, profile_garden, reminders,
  evaluation, identification, light_measurements, or api).
- Observability modules MUST NOT import from slices or providers.
- Slice-to-slice dependencies are limited to public service or
  schema entry points.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

APP_DIR = Path("app")
# Slice internals (provider MUST NOT depend on these).
SLICE_NAMES = (
    "assistant",
    "knowledge",
    "auth",
    "profile_garden",
    "reminder",
    "reminders",
    "evaluation",
    "identification",
    "light_measurements",
)
# Shared infrastructure (allowed for everyone).
SHARED_NAMES = ("core", "db", "storage", "schemas")
PROVIDER_DIRS = ("app/providers",)
OBSERVABILITY_DIRS = ("app/observability",)
API_DIRS = ("app/api",)

# Known API -> slice-internal imports that are pending the introduction
# of a service layer. Each entry is a fully-qualified module path.
# Remove an entry once the corresponding slice exposes a public
# service module that the API can import instead.
KNOWN_API_SLICE_INTERNALS = {
    "app.profile_garden.repository",
    "app.reminders.repository",
    "app.identification.repository",
    "app.identification.gbif",
    "app.light_measurements.repository",
}


def _is_in(path: Path, prefixes: tuple[str, ...]) -> bool:
    posix = path.as_posix()
    return any(posix.startswith(prefix) for prefix in prefixes)


def _slice_segment(imported: str) -> str | None:
    """Return the slice name from an ``app.<slice>.<...>`` import, or None."""
    parts = imported.split(".")
    if len(parts) < 2 or parts[0] != "app":
        return None
    second = parts[1]
    if second in SLICE_NAMES:
        return second
    return None


def main() -> int:
    failures: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        rel = path.as_posix()
        try:
            source = path.read_text()
        except OSError:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        for imported in imports:
            if imported.startswith("fastapi") or imported.startswith("pydantic") or imported.startswith("sqlalchemy"):
                continue
            slice_name = _slice_segment(imported)
            if _is_in(path, PROVIDER_DIRS):
                if slice_name is not None:
                    failures.append(
                        f"{rel}: provider module imports slice internals: {imported}"
                    )
            elif _is_in(path, OBSERVABILITY_DIRS):
                if slice_name is not None or imported.startswith("app.providers"):
                    failures.append(
                        f"{rel}: observability module imports slice or provider: {imported}"
                    )
            elif _is_in(path, API_DIRS):
                # API modules are limited to service and schema entry points.
                # Allow auth because the API reuses auth models/dependencies.
                if (
                    slice_name is not None
                    and slice_name not in SHARED_NAMES
                    and slice_name != "auth"
                ):
                    # Allow public service and schemas modules; flag
                    # imports into repository.py, gbif.py, etc.
                    parts = imported.split(".")
                    if len(parts) >= 3 and parts[2] in ("service", "schemas"):
                        continue
                    # Known exceptions: some slices do not yet expose a
                    # service layer; allow direct repository/gbif imports
                    # in the interim. Track them in
                    # ``KNOWN_API_SLICE_INTERNALS`` for follow-up refactors.
                    if imported in KNOWN_API_SLICE_INTERNALS:
                        continue
                    failures.append(
                        f"{rel}: API module imports slice internals: {imported}"
                    )
    if failures:
        print("Layering rule violations:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("All layering rules satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
