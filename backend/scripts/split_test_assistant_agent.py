"""Split test_assistant_agent.py into focused files under 1,000 lines each.

This script reads the source test file, extracts the shared helpers
(classes, constants, helper functions) into ``_assistant_helpers.py``,
and then emits a series of focused test files that each include the
shared header (imports) plus a slice of test functions.
"""

from __future__ import annotations

import re
from pathlib import Path

INPUT = Path("tests/test_assistant_agent.py")
OUTPUT_DIR = Path("tests")
NUM_FILES = 12
PREFIX = "test_assistant_agent_part"
HELPERS_PATH = Path("tests/_assistant_helpers.py")
HEADER_END_MARKER = re.compile(
    r"^def test_classify_care_message_no_longer_references_classifier_model_helper",
    re.MULTILINE,
)
DEFINITION_RE = re.compile(r"^(async def |def |class )")
DECORATOR_RE = re.compile(r"^@")

# Shared symbols that must be available in every test part. These are
# the class names and helper functions used across many tests.
SHARED_HELPER_SYMBOLS = {
    "FakeTools",
    "RollbackRecordingKnowledgeRepository",
    "_structured_evidence",
    "_validated_web_metadata",
    "StrongWateringJudgeTools",
    "LowConfidenceSafetyJudgeTools",
    "PartialLowConfidenceJudgeTools",
    "HighConfidencePartialJudgeTools",
    "SlowJudgeTools",
    "SlowWebSearchTools",
}

# Shared module-level constants that must be available in every test part.
SHARED_CONSTANT_NAMES = {
    "CONFIRMED_BINOMIAL",
    "PEST_CLASSIFIER",
    "SAFETY_PET_CLASSIFIER",
    "CHEMICAL_TREATMENT_CLASSIFIER",
    "PESTICIDE_INSTRUCTION_CLASSIFIER",
    "SAFETY_BOUNDARY_CASES",
}


def main() -> None:
    text = INPUT.read_text()
    lines = text.splitlines(keepends=True)
    header_match = HEADER_END_MARKER.search(text)
    if not header_match:
        raise SystemExit("header marker not found")
    header_end_line = text[: header_match.start()].count("\n")
    header = "".join(lines[:header_end_line])

    # Walk the body and collect unit starts (def/class with decorators).
    body_lines = lines[header_end_line:]
    def_line_indices: list[int] = []
    for idx, line in enumerate(body_lines):
        if DEFINITION_RE.match(line):
            def_line_indices.append(idx)
    unit_starts: list[int] = []
    for line_index in def_line_indices:
        start = line_index
        while start > 0 and DECORATOR_RE.match(body_lines[start - 1]):
            start -= 1
        unit_starts.append(start)

    body = "".join(body_lines)
    body_offsets: list[int] = []
    running = 0
    for line in body_lines:
        body_offsets.append(running)
        running += len(line)

    # Identify which units are shared helpers and shared constants.
    helper_units: list[tuple[int, int, str]] = []  # (start_line, end_line, name)
    for i, line_index in enumerate(def_line_indices):
        line = body_lines[line_index]
        name = line.split(":", 1)[0].split("(")[0].split()[-1]
        if name in SHARED_HELPER_SYMBOLS:
            next_start = (
                unit_starts[i + 1] if i + 1 < len(unit_starts) else len(body_lines)
            )
            helper_units.append((unit_starts[i], next_start, name))

    # Identify constant blocks. The shared constants are top-level
    # assignments at module level (not inside functions). For each
    # SHARED_CONSTANT_NAMES entry, find the line and extend to the
    # closing bracket of the literal, walking forward through any
    # nested brackets.
    constant_block_ranges: list[tuple[int, int]] = []
    constant_starts: list[tuple[int, str]] = []
    for idx, line in enumerate(body_lines):
        stripped = line.strip()
        for name in SHARED_CONSTANT_NAMES:
            if stripped.startswith(f"{name} = ") or stripped.startswith(f"{name}="):
                constant_starts.append((idx, name))
                break

    def _find_block_end(start: int) -> int:
        """Find the line AFTER the closing bracket of the constant literal."""
        depth = 0
        for j in range(start, len(body_lines)):
            line = body_lines[j]
            for ch in line:
                if ch in "[{(":
                    depth += 1
                elif ch in "]})":
                    depth -= 1
                    if depth == 0 and "=" in line:
                        return j + 1
            if depth == 0 and j > start and "=" not in line and "[" not in line and "{" not in line:
                # Multi-line constant without brackets — end at the next def/class
                return j + 1
        return len(body_lines)

    for i, (start, _name) in enumerate(constant_starts):
        end = _find_block_end(start)
        constant_block_ranges.append((start, end))

    # Build the shared helpers section. Each unit/constant block is
    # converted to a byte slice using body_offsets. We also include
    # the test unit that follows a constant block when the test
    # consumes the constant (e.g. via parametrize). Each consumed
    # test is added at most once.
    def _slice_to_text(start_line: int, end_line: int) -> str:
        start_offset = body_offsets[start_line]
        end_offset = (
            body_offsets[end_line] if end_line < len(body_offsets) else len(body)
        )
        return body[start_offset:end_offset].rstrip()

    consumed_constant_followups_for_helpers: set[int] = set()

    def _find_consumed_followup(end_line: int) -> int | None:
        for j in range(end_line, len(body_lines)):
            if DEFINITION_RE.match(body_lines[j]):
                if j in consumed_constant_followups_for_helpers:
                    return None  # already added
                consumed_constant_followups_for_helpers.add(j)
                return j
        return None

    # Write the helpers module: the original header (imports) plus
    # the helper units and constant blocks. The block ends extend to
    # include any consumed test unit so the parametrize/import works.
    helpers_chunks: list[str] = []
    for start_line, end_line, _ in helper_units:
        helpers_chunks.append(_slice_to_text(start_line, end_line))
    for start_line, end_line in constant_block_ranges:
        # Extend the block to include the consumed test def (if any).
        extended_end = end_line
        followup = _find_consumed_followup(end_line)
        if followup is not None:
            # Find the end of the consumed test
            idx = def_line_indices.index(followup)
            next_start = (
                unit_starts[idx + 1] if idx + 1 < len(unit_starts) else len(body_lines)
            )
            extended_end = next_start
        helpers_chunks.append(_slice_to_text(start_line, extended_end))
    HELPERS_PATH.write_text(
        "from __future__ import annotations\n\n"
        + "# Auto-generated by scripts/split_test_assistant_agent.py\n"
        + "# Shared helpers and constants used across the focused test files.\n\n"
        + header
        + "\n\n\n".join(helpers_chunks)
        + "\n"
    )
    print(f"Wrote {HELPERS_PATH}")

    # Now exclude shared helpers/constants from each chunk so the parts
    # only contain the test functions themselves.
    helper_line_ranges: set[tuple[int, int]] = set()
    for start_line, end_line, _ in helper_units:
        helper_line_ranges.add((start_line, end_line))
    for start_line, end_line in constant_block_ranges:
        helper_line_ranges.add((start_line, end_line))

    # Build the list of unit byte offsets (start, end) for slicing,
    # skipping any unit that is a shared helper. We also skip a unit
    # whose first line (after decorators) is the line right after a
    # constant block — that means the test consumes the constant via a
    # parametrize decorator.
    non_helper_unit_offsets: list[tuple[int, int]] = []
    consumed_constant_followups: set[int] = set()
    for start_line, end_line in constant_block_ranges:
        # Look at the next def after this block and skip it.
        for j in range(end_line, len(body_lines)):
            if DEFINITION_RE.match(body_lines[j]):
                consumed_constant_followups.add(j)
                break
    for i, line_index in enumerate(def_line_indices):
        if any(start == line_index for start, _ in helper_line_ranges):
            continue
        # Find end of this unit
        unit_end_line = (
            unit_starts[i + 1] if i + 1 < len(unit_starts) else len(body_lines)
        )
        # Skip if the entire unit is inside a helper range
        if any(
            start <= line_index and unit_end_line <= end
            for start, end in helper_line_ranges
        ):
            continue
        # Skip units that consume a constant (the test def follows the block).
        if line_index in consumed_constant_followups:
            continue
        start_offset = body_offsets[line_index]
        end_offset = (
            body_offsets[unit_end_line] if unit_end_line < len(body_offsets) else len(body)
        )
        non_helper_unit_offsets.append((start_offset, end_offset))

    # Build shared imports footer (so test parts can use the helpers)
    helpers_import = "from tests._assistant_helpers import (\n"
    for name in sorted(SHARED_HELPER_SYMBOLS):
        helpers_import += f"    {name},\n"
    helpers_import += ")\n"
    for name in sorted(SHARED_CONSTANT_NAMES):
        helpers_import += f"from tests._assistant_helpers import {name}\n"

    # Distribute non-helper units across NUM_FILES chunks, balanced.
    total_units = len(non_helper_unit_offsets)
    if total_units == 0:
        raise SystemExit("no test units to split")
    chunk_size = (total_units + NUM_FILES - 1) // NUM_FILES
    for chunk_index in range(NUM_FILES):
        start_idx = chunk_index * chunk_size
        end_idx = min((chunk_index + 1) * chunk_size, total_units)
        if start_idx >= total_units:
            break
        # Concatenate the unit bodies for this chunk.
        chunk_body = "".join(
            body[start:end].rstrip() + "\n\n"
            for start, end in non_helper_unit_offsets[start_idx:end_idx]
        )
        combined = header + helpers_import + "\n\n" + chunk_body
        out_path = OUTPUT_DIR / f"{PREFIX}{chunk_index + 1}.py"
        out_path.write_text(combined)
        line_count = combined.count("\n")
        print(
            f"Wrote {out_path}: {end_idx - start_idx} tests, {line_count} lines"
        )


if __name__ == "__main__":
    main()
