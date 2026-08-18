## Context

The assistant graph already reaches `handle_action` and calls `light_measurement_lookup`, but a non-empty successful result is neither returned nor stored in assistant state, so the success path falls through without a measurement-grounded recommendation. Light measurements are persisted with source, reliability, plant, and timestamp, and the assistant can query the latest measurement for a selected garden plant. The multilingual classifier is the existing semantic authority, and confirmed-plant context is already resolved server-side.

## Goals / Non-Goals

**Goals:**

- Let the classifier indicate, semantically and schema-validated, whether light context is relevant.
- Retrieve and retain an eligible measurement for the selected plant, and pass it into grounded synthesis as a contextual observation.
- Disclose source, age, reliability, and approximation, and reuse the same eligibility policy for reminder suggestions.

**Non-Goals:**

- No camera calibration by device model, no permanent placement conclusions, no replacing evidence retrieval with sensor observations, no longitudinal care-plan entity.

## Decisions

- **Extend the classifier contract with a bounded light-context relevance signal** rather than inferring relevance from keywords. This keeps the multilingual classifier as the semantic authority and satisfies the project rule against hardcoded language heuristics.
- **Apply a single eligibility check** (owner and selected-plant scope, supported source/units, minimum reliability, per-source freshness threshold) in the graph before retaining a measurement. Configurable thresholds live in settings, not a data-model migration.
- **Retain the eligible measurement in assistant state** and pass it into answer synthesis as a contextual observation, kept distinct from species-level botanical evidence. The answer discloses date, source, reliability, and approximate status.
- **Reuse the same eligibility policy** for reminder-suggestion context so care answers and reminder justifications stay consistent.

## Risks / Trade-offs

- A single reading can mislead → the answer preserves age, reliability, and limitations and avoids categorical conclusions.
- Source units may differ → unsupported units are rejected conservatively rather than converted.
- Classifier over-selection can add lookup calls → tests cover clearly unrelated requests.
- Old records may lack metadata → treat them as ineligible rather than inferring values.
- Measurement details are user data → ownership checks and bounded logging remain required.
