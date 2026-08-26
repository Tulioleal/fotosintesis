## 1. Schemas and Settings

- [x] 1.1 Extend the classifier contract schema with a bounded, schema-validated light-context relevance signal and enforce it through the existing validation path.
- [x] 1.2 Extend assistant state with a bounded light-context need and a retained measurement shape (value/classification, source, timestamp, age, reliability, approximate flag).
- [x] 1.3 Add configurable per-source freshness thresholds and a minimum reliability threshold with safe defaults.

## 2. Eligibility

- [x] 2.1 Implement a single eligibility check covering owner and selected-plant scope, supported source and units, minimum reliability, and per-source freshness.

## 3. Graph Integration

- [x] 3.1 Perform the light-measurement lookup only when the classifier signals relevance, and skip it for unrelated requests.
- [x] 3.2 Retain a successful eligible lookup result in assistant state through `handle_action` instead of discarding it.
- [x] 3.3 Pass the retained measurement into grounded synthesis as a contextual observation, kept distinct from species-level evidence.
- [x] 3.4 Disclose date, source, reliability, and approximate status when a measurement influences the answer, and recommend remeasurement when relevant context is missing or ineligible.

## 4. Reminder Suggestions

- [x] 4.1 Apply the same eligibility policy to reminder-suggestion light context and disclosure.

## 5. Verification

- [x] 5.1 Add a graph-path regression proving a successful eligible lookup survives `handle_action` and reaches answer synthesis.
- [x] 5.2 Add tests covering recent, stale, unreliable, absent, foreign-plant, and irrelevant cases.
- [x] 5.3 Add regression tests proving non-English and paraphrased relevance reaches the semantic path without keyword matches.
- [x] 5.4 Run backend and frontend lint, typecheck, and test suites.
