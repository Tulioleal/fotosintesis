## Why

The assistant's plant-care classification contract is too coarse for real-world questions about symptoms, diagnosis, pests, diseases, recovery, propagation, nutrition, seasonal behavior, safety, and multi-factor decline. Some required aspects are generic and depend on `CareTopic` for interpretation, which creates ambiguity across classification, answerability validation, diagnostics, and web fallback query construction.

## What Changes

- Expand `CareTopic` to cover more explicit plant-care domains such as diagnosis, pests, disease, repotting, pruning, propagation, climate, humidity, growth, flowering or fruiting, seasonality, toxicity and safety, taxonomy, ecology, and general care.
- Expand `RequiredAspect` into domain-qualified, self-descriptive values such as `pest_treatment_action`, `disease_prevention_steps`, and `diagnosis_urgency_level`.
- Remove or avoid ambiguous generic required aspects outside the `general_*` domain.
- Update deterministic and LLM classifier guidance so required aspects are selected directly from the user request and never disambiguated by topic alone.
- Update answerability, evidence validation, diagnostics, and web fallback query construction to use domain-qualified required aspects consistently.
- Update tests and expected enum values for the expanded taxonomy and regression cases.
- **BREAKING**: Existing required-aspect enum values that are generic or renamed must be migrated in tests and internal contracts; persisted diagnostics containing old values may need compatibility handling if they are read after deployment.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Update the plant-care classifier contract, topic taxonomy, required-aspect taxonomy, diagnostic metadata, and response behavior for diagnosis and safety-sensitive requests.
- `knowledge-rag-acquisition`: Update runtime retrieval, evidence validation, and trusted web fallback requirements to use domain-qualified required aspects for coverage and query targeting.
- `rag-contextual-validation`: Update safety-sensitive threshold selection to recognize the new toxicity and safety aspect names instead of generic legacy names.

## Impact

- Backend classifier contract and enums in `backend/app/assistant/care_contracts.py`.
- Deterministic classification helpers, LLM classifier prompts, answerability judge prompts, conservative evidence matching, and web fallback query generation.
- Assistant diagnostics and response metadata that expose selected topic and required aspects.
- Backend tests for classification, answerability validation, diagnostics, fallback query generation, and taxonomy regression cases.
