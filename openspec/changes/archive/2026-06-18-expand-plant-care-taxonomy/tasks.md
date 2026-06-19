## 1. Taxonomy Contract

- [x] 1.1 Update `CareTopic` in `backend/app/assistant/care_contracts.py` to include the expanded canonical topic set.
- [x] 1.2 Replace ambiguous `RequiredAspect` values with the expanded domain-qualified taxonomy, keeping only `general_*` values generic by design.
- [x] 1.3 Update any schema validation, serialization, or compatibility helpers that enumerate care topics or required aspects.
- [x] 1.4 Add a narrow legacy-aspect translation only if implementation finds persisted or externally read old diagnostic values that must remain readable.

## 2. Classification

- [x] 2.1 Update the schema-valid LLM classifier contract and prompt guidance to emit the new domain-qualified required aspects for watering, light, soil, pot, nutrition, diagnosis, pests, disease, repotting, pruning, propagation, climate, humidity, growth, flowering or fruiting, seasonality, toxicity and safety, taxonomy, ecology, and general care requests.
- [x] 2.2 Ensure broad symptom questions prefer `diagnosis_*` aspects and do not add watering, nutrition, pest, or disease aspects unless explicitly requested or strongly implied by schema-valid LLM classifier output.
- [x] 2.3 Keep deterministic fallback routing minimal; it must not emit detailed botanical topics or domain-qualified required aspects from keyword rules, translated word lists, regexes, or substring checks.
- [x] 2.4 Ensure classifier repair and validation reject unknown or legacy generic aspect names in new classifier output.

## 3. Evidence And Answerability

- [x] 3.1 Update answerability judge guidance so coverage is evaluated independently for each requested domain-qualified aspect.
- [x] 3.2 Update answerability normalization so `covered_aspects` and `missing_aspects` remain subsets of the requested canonical aspect values.
- [x] 3.3 Update safety-sensitive aspect detection to use `toxicity_*` and applicable `safety_*` values with the strict safety threshold.
- [x] 3.4 Update conservative evidence keyword groups for the expanded aspects without letting keyword mismatch override coherent semantic support.
- [x] 3.5 Ensure diagnosis answers present causes as hypotheses unless direct evidence supports a definitive claim.

## 4. Retrieval, Web Fallback, And Diagnostics

- [x] 4.1 Update enriched RAG query construction to include the new domain-qualified required aspect names.
- [x] 4.2 Update trusted web fallback query construction to convert domain-qualified aspect names into useful natural-language search terms.
- [x] 4.3 Ensure web fallback uses missing domain-qualified aspects directly and does not rely on `CareTopic` to disambiguate them.
- [x] 4.4 Ensure response diagnostics expose the expanded `topic`, `required_aspects`, `covered_aspects`, and `missing_aspects` exactly as canonical enum values.
- [x] 4.5 Review ingestion or persisted metadata paths that store `required_aspects` and update expected values or compatibility handling as needed.

## 5. Tests And Verification

- [x] 5.1 Update existing tests and fixtures that reference old topic or required-aspect values.
- [x] 5.2 Add classifier regression tests for simple watering, light, toxicity, symptom diagnosis, pests, disease, repotting, pruning, propagation, nutrition, climate, humidity, taxonomy, ecology, and general-care requests.
- [x] 5.3 Add regression tests ensuring symptom questions select `diagnosis_*` aspects instead of unrelated care-routine aspects unless explicitly requested.
- [x] 5.4 Add answerability tests rejecting full status when any requested domain-qualified aspect is missing.
- [x] 5.5 Add safety-threshold tests for `toxicity_*` and applicable `safety_*` aspects.
- [x] 5.6 Add web fallback query tests proving domain-qualified aspects produce precise natural-language search terms.
- [x] 5.7 Add diagnostics tests proving expanded canonical topic and aspect values are exposed consistently.
- [x] 5.8 Run the relevant backend test suite and targeted assistant tests, then fix any regressions.
