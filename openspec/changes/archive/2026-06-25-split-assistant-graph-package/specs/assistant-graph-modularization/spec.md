## ADDED Requirements

### Requirement: Assistant graph package structure
The system SHALL implement the assistant graph as a package under `app/assistant/graph/` with focused submodules for graph contracts, constants, helpers, classifier behavior, answerability behavior, web evidence behavior, answer generation behavior, prompt builders, safety behavior, plant resolution behavior, route predicates, graph topology, and the facade class.

#### Scenario: Graph package exists with concern-owned modules
- **WHEN** a developer inspects `app/assistant/graph/`
- **THEN** the package contains concern-owned modules for `types`, `constants`, `helpers`, `classifier`, `answerability`, `web_evidence`, `answers`, `prompts`, `safety`, `plant_resolution`, `routes`, `topology`, and `facade`

#### Scenario: Monolithic implementation is removed from shim
- **WHEN** a developer opens `app/assistant/graph/__init__.py`
- **THEN** it contains only compatibility imports and exports, not assistant graph business logic
- **NOTE:** The shim is the package init file rather than a sibling `app/assistant/graph.py` file because Python cannot have both a `graph.py` file and a `graph/` package directory sharing the same parent. The package init plays the same role for `from app.assistant.graph import X` resolution.

### Requirement: Public import compatibility
The system SHALL preserve the existing public import surface from `app.assistant.graph` through a compatibility shim.

#### Scenario: Public assistant graph symbols remain importable
- **WHEN** code imports `AssistantGraph`, `AssistantState`, `FallbackResponseDraft`, or `AnswerabilityResult` from `app.assistant.graph`
- **THEN** the import succeeds and resolves to the implementation provided by the new graph package

#### Scenario: Existing test-imported private helpers remain importable
- **WHEN** existing tests import previously exposed helper symbols from `app.assistant.graph`
- **THEN** those imports continue to succeed through shim re-exports

### Requirement: Canonical symbol ownership
The system SHALL define each moved symbol in exactly one canonical graph submodule and re-export it from the shim only for compatibility.

#### Scenario: Type contracts have a canonical module
- **WHEN** code imports assistant graph contracts from `app.assistant.graph.types`
- **THEN** `AssistantState`, `FallbackResponseDraft`, and `AnswerabilityResult` are available from that module

#### Scenario: Classifier symbols have a canonical module
- **WHEN** code imports classifier-owned helpers from `app.assistant.graph.classifier`
- **THEN** classifier prompt builders, classifier retry handling, invalid-output logging, deterministic fallback classification, and legacy intent translation helpers are available from that module

#### Scenario: Answerability symbols have a canonical module
- **WHEN** code imports answerability-owned helpers from `app.assistant.graph.answerability`
- **THEN** judge conversion, answerability validation, source-support validation, contradiction validation, combined-evidence judging, diagnostics, and recoverable-generation-failure helpers are available from that module

#### Scenario: Web evidence symbols have a canonical module
- **WHEN** code imports web-evidence helpers from `app.assistant.graph.web_evidence`
- **THEN** targeted web query helpers, reusable web candidate helpers, web metadata helpers, claim payload helpers, and source extraction helpers are available from that module

#### Scenario: Answer-generation symbols have a canonical module
- **WHEN** code imports answer-generation helpers from `app.assistant.graph.answers`
- **THEN** fallback draft builders, fallback response generation, structured answer generation, web answer generation, grounded answer generation, disclaimed guidance generation, and answer cleanup helpers are available from that module

#### Scenario: Prompt symbols have a canonical module
- **WHEN** code imports prompt builders from `app.assistant.graph.prompts`
- **THEN** grounded-answer and general-disclaimer prompt builders are available from that module

#### Scenario: Safety symbols have a canonical module
- **WHEN** code imports safety helpers from `app.assistant.graph.safety`
- **THEN** safety-sensitive question checks, missing safety aspect checks, requested safety aspect checks, and relevant plant-context checks are available from that module

#### Scenario: Plant resolution symbols have a canonical module
- **WHEN** code imports plant-resolution helpers from `app.assistant.graph.plant_resolution`
- **THEN** operational name selection, display name selection, name normalization, binomial extraction, taxonomy context, selected-plant resolution, and selected-plant confirmation helpers are available from that module

#### Scenario: Routing symbols have a canonical module
- **WHEN** code imports route predicates from `app.assistant.graph.routes`
- **THEN** context, sufficiency, web fallback, failure, and disclaimed-guidance eligibility route helpers are available from that module

#### Scenario: Topology symbols have a canonical module
- **WHEN** code imports graph topology helpers from `app.assistant.graph.topology`
- **THEN** graph compilation and sequential fallback execution helpers are available from that module

### Requirement: AssistantGraph facade delegates behavior
The system SHALL keep `AssistantGraph` as the public runtime facade while moving business logic out of the class body into concern-owned submodules.

#### Scenario: AssistantGraph methods delegate to submodules
- **WHEN** a developer inspects `app.assistant.graph.facade.AssistantGraph`
- **THEN** node/helper methods delegate to functions in the owning submodules instead of containing full business logic bodies

#### Scenario: AssistantGraph construction remains compatible
- **WHEN** `AssistantService` constructs `AssistantGraph(tools, settings)`
- **THEN** construction succeeds with the same constructor signature and initializes graph execution as before

#### Scenario: AssistantGraph run behavior remains compatible
- **WHEN** an assistant chat flow invokes `AssistantGraph.run(...)`
- **THEN** the method accepts the same inputs, returns the same state shape, clears and appends provider fallback context as before, and invokes the compiled graph as before

### Requirement: Graph topology remains unchanged
The system SHALL preserve the assistant graph topology and sequential fallback execution semantics after moving topology code to `app.assistant.graph.topology`.

#### Scenario: Compiled graph preserves nodes and routes
- **WHEN** topology tests inspect the compiled assistant graph
- **THEN** the graph exposes the same node names and route decisions as before the package split

#### Scenario: Sequential fallback preserves execution order
- **WHEN** the sequential fallback graph is used instead of LangGraph compilation
- **THEN** it invokes the assistant flow in the same order and applies the same route predicates as before the package split

### Requirement: Canonical monkeypatch targets
The system SHALL update tests to monkeypatch canonical submodule paths where implementation symbols now live.

#### Scenario: Answerability monkeypatches target answerability module
- **WHEN** a test patches answerability judging behavior
- **THEN** it patches symbols under `app.assistant.graph.answerability` rather than the `app.assistant.graph` shim

#### Scenario: Prompt monkeypatches target prompt module
- **WHEN** a test patches prompt construction behavior
- **THEN** it patches symbols under `app.assistant.graph.prompts` rather than the `app.assistant.graph` shim

#### Scenario: Web evidence monkeypatches target web evidence module
- **WHEN** a test patches web query or web evidence behavior
- **THEN** it patches symbols under `app.assistant.graph.web_evidence` rather than the `app.assistant.graph` shim

### Requirement: Aspect validation guidance naming is unambiguous
The system SHALL preserve the existing public `aspect_validation_guidance` import while exposing the graph-internal dict-producing helper under a distinct name.

#### Scenario: Public aspect metadata helper keeps its name
- **WHEN** code imports `aspect_validation_guidance` from `app.assistant.graph`
- **THEN** the shim exposes the existing `app.assistant.aspect_metadata.aspect_validation_guidance` behavior

#### Scenario: Graph-internal guidance helper has a graph-specific name
- **WHEN** graph answerability code needs a `dict[str, str]` of validation guidance for required aspects
- **THEN** it uses `_graph_aspect_validation_guidance` from `app.assistant.graph.answerability`

#### Scenario: No caller depends on the old ambiguous internal name
- **WHEN** implementation verification searches for callers of the graph-internal guidance helper under the bare public name
- **THEN** no runtime caller depends on that ambiguous name

### Requirement: Behavior-preserving refactor
The system SHALL not change assistant runtime behavior as part of this package split.

#### Scenario: HTTP and schema contracts remain unchanged
- **WHEN** the backend exposes assistant API endpoints after the split
- **THEN** request schemas, response schemas, OpenAPI output, and route behavior remain compatible with the pre-split implementation

#### Scenario: Semantic assistant behavior remains unchanged
- **WHEN** classifier, answerability, evidence validation, safety routing, fallback routing, and answer generation tests run after the split
- **THEN** they continue to pass without introducing new deterministic keyword lists, translated word lists, language-specific heuristics, or regex-based botanical semantics

### Requirement: Graph submodules respect file-size boundaries
The system SHALL keep each module under `app/assistant/graph/` below 500 lines after the split.

#### Scenario: Assistant graph file-size verification passes
- **WHEN** file-size verification runs against `app/assistant/graph/*.py`
- **THEN** no graph submodule exceeds 500 lines

#### Scenario: Shim remains small
- **WHEN** file-size verification runs against `app/assistant/graph/__init__.py`
- **THEN** the compatibility shim remains approximately 50 lines and contains no business logic
- **NOTE:** The shim is the package init file rather than a sibling `app/assistant/graph.py` file because Python cannot have both a `graph.py` file and a `graph/` package directory sharing the same parent.
