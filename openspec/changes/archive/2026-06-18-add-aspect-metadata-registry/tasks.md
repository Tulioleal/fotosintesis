## 1. Metadata Registry

- [x] 1.1 Add `backend/app/assistant/aspect_metadata.py` with `RequiredAspectMetadata`, `REQUIRED_ASPECT_METADATA`, and helper functions for metadata lookup, query terms, validation guidance, and safety sensitivity.
- [x] 1.2 Move existing aspect validation guidance into registry entries, preserving current watering, diagnosis, and toxicity coverage behavior.
- [x] 1.3 Add metadata entries for all current `RequiredAspect` values with at least domain, label, query label, and search terms.
- [x] 1.4 Mark toxicity and safety-related aspects as safety-sensitive in metadata and keep compatibility with existing `SAFETY_SENSITIVE_ASPECTS` imports where needed.

## 2. Assistant Pipeline Integration

- [x] 2.1 Replace `_aspect_validation_guidance()` behavior with metadata-driven guidance that includes only requested aspects with `coverage_guidance`.
- [x] 2.2 Update answerability judge payload construction and rubric text so coverage decisions rely on metadata guidance without hardcoding watering-specific guidance in the graph.
- [x] 2.3 Update `_targeted_web_query()` to use metadata query labels and search terms for missing aspects, dedupe terms, and preserve safe enum-derived fallback text.
- [x] 2.4 Remove deterministic keyword gating from snippet/content eligibility; trusted evidence reaches the judge without keyword matching.
- [x] 2.5 Update safety-sensitive threshold decisions and safety fallback checks to use `is_safety_sensitive_aspect()` where practical.
- [x] 2.6 Preserve canonical aspect strings in `required_aspects`, `covered_aspects`, and `missing_aspects`, and add readable diagnostic labels only as additive metadata if implemented.

## 3. Tests

- [x] 3.1 Add metadata unit tests covering enum and string lookup, unknown-aspect fallback, one guided aspect, one unguided aspect, and one safety-sensitive aspect.
- [x] 3.2 Update answerability guidance tests to assert watering guidance comes from metadata and unguided aspects are omitted from the judge payload.
- [x] 3.3 Update targeted web query tests to assert metadata-derived query labels or search terms appear instead of only underscore-expanded enum values.
- [x] 3.4 Add or update safety threshold tests to assert metadata-marked safety aspects use `assistant_safety_validation_threshold` and non-safety strong results use the strong threshold.
- [x] 3.5 Add regression tests asserting non-English snippets reach the judge without keyword filtering.

## 4. Verification

- [x] 4.1 Run the assistant backend test module that covers aspect validation and web fallback behavior.
- [x] 4.2 Run the focused metadata tests added for this change.
- [x] 4.3 Run OpenSpec validation/status for `add-aspect-metadata-registry` and confirm the change is apply-ready.
