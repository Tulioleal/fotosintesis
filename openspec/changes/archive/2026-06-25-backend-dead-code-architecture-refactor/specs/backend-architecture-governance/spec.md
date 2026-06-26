## ADDED Requirements

### Requirement: Verified dead code removal

The backend refactor SHALL remove only code that has been verified as unused or limited to obsolete test-only paths, including unused schema files, unused provider or observability helpers, unused assistant tool methods, unused settings fields, duplicate helpers, and tracked build artifacts.

#### Scenario: Dead code sweep preserves runtime behavior
- **WHEN** the dead-code sweep phase is complete
- **THEN** `ruff check app/ tests/` and `pytest -x` pass
- **AND** the HTTP API surface, provider selection behavior, and LangGraph runtime behavior remain unchanged

#### Scenario: Build artifacts are ignored
- **WHEN** repository ignore rules are inspected after the dead-code sweep
- **THEN** Python cache directories and `*.egg-info/` build output directories are ignored by source control

### Requirement: Behavior-preserving module decomposition

The backend refactor SHALL split oversized modules in `app/assistant/`, `app/providers/`, and `app/knowledge/` into cohesive capability packages while preserving existing public import paths through temporary re-export shims until dependent tests and imports have moved.

#### Scenario: Existing imports remain valid during migration
- **WHEN** a source file is converted from a module into a package during phases 3 through 8
- **THEN** the previous module path continues to expose the same public symbols through a temporary re-export shim

#### Scenario: Shims are removed after test migration
- **WHEN** tests and application imports have been moved to the new module paths
- **THEN** temporary re-export shims introduced for the refactor are removed before final architecture enforcement

### Requirement: Provider layer independence

Provider modules SHALL NOT import assistant, knowledge, auth, profile, reminder, evaluation, API, or other feature-slice internals. Shared provider JSON schemas, schema normalization, strict-mode formatting, provider errors, and fallback behavior SHALL live under `app/providers/`.

#### Scenario: Gemini provider no longer depends on assistant internals
- **WHEN** provider imports are inspected after provider package extraction
- **THEN** Gemini provider code does not import from `app/assistant/`
- **AND** judge, vision, and classifier schema shapes used by providers are sourced from `app/providers/schemas/`

#### Scenario: Provider fallback behavior uses a shared runner
- **WHEN** provider fallback wrappers are inspected after wrapper extraction
- **THEN** model, search, vision, and embeddings fallback wrappers delegate repeated chain execution behavior to a shared runner
- **AND** provider-specific unusable-result handling is expressed as an explicit hook or callback

### Requirement: Assistant graph topology preservation

The assistant graph refactor SHALL preserve the compiled LangGraph node and edge topology while moving classifier, answerability, safety, prompt, source, plant-resolution, answer-generation, diagnostics, and fallback responsibilities into capability modules.

#### Scenario: Topology test protects graph structure
- **WHEN** the assistant graph split begins
- **THEN** a graph topology test exists that records the expected compiled node and edge list
- **AND** the test passes after each graph split sub-phase

#### Scenario: Semantic plant-care behavior remains model and evidence driven
- **WHEN** assistant classifier, answerability, evidence validation, retrieval eligibility, or language handling code is inspected after the split
- **THEN** semantic botanical decisions are still handled through multilingual classifier outputs, schema-validated model responses, semantic answerability judging, structured taxonomy/aspect metadata, or source-grounded evidence
- **AND** the implementation does not introduce hardcoded keyword lists, translated word lists, regex language detection, substring checks, or English/Spanish-only heuristics for semantic plant-care behavior

### Requirement: Test suite decomposition

The assistant integration test file SHALL be split into focused test files that preserve existing coverage and keep each test file within the configured hard size cap.

#### Scenario: Split tests preserve coverage targets
- **WHEN** the large assistant test file is split
- **THEN** existing test names remain searchable in the resulting test files
- **AND** `pytest -x` passes after each sub-split

#### Scenario: Test file size cap is respected
- **WHEN** final architecture enforcement runs
- **THEN** no test file exceeds the configured hard cap of 1,000 lines

### Requirement: Architecture and file-size enforcement

The backend SHALL include automated checks that enforce backend layering rules and file-size hard caps after the refactor completes.

#### Scenario: Source file size caps are enforced
- **WHEN** the architecture file-size check runs in CI
- **THEN** provider adapter modules, slice services, slice internals, graph node or route modules, prompt modules, and tests are checked against their configured hard caps
- **AND** the check fails if any file exceeds its hard cap

#### Scenario: Layering rules are enforced
- **WHEN** the architecture layering check runs in CI
- **THEN** API modules are limited to service and schema entry points
- **AND** provider modules are prevented from importing feature-slice internals
- **AND** observability modules are prevented from importing slices or providers
- **AND** slice-to-slice dependencies are limited to service or port entry points

### Requirement: Final verification gates

The completed refactor SHALL pass linting, tests, file-size checks, layering checks, graph topology verification, and OpenAPI compatibility verification before being considered implementation-ready for archive.

#### Scenario: Final verification succeeds
- **WHEN** all refactor phases are complete
- **THEN** `ruff check app/ tests/` passes
- **AND** `pytest` passes
- **AND** the file-size and layering checks pass
- **AND** the compiled LangGraph node and edge list matches the pre-refactor topology expectation
- **AND** the generated OpenAPI schema is unchanged from the pre-refactor baseline
