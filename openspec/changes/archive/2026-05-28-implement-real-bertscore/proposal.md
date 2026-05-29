## Why

The evaluation report currently labels a token-overlap F1 calculation as BERTScore, which can overstate semantic evaluation quality and mislead regression analysis. This change makes referenced text evaluation use a real embedding/model-based BERTScore implementation or fail clearly when unavailable.

## What Changes

- Replace the local token-overlap `bertscore` implementation with an actual BERTScore-backed metric for referenced text outputs.
- Add the required backend dependency and deterministic configuration needed to compute precision, recall and F1 consistently in offline evaluation runs.
- Update evaluation report wording so it no longer describes BERTScore as a dependency-free token F1 approximation.
- Preserve the existing metric output shape: `precision`, `recall` and `f1` floats.
- Add tests that distinguish semantic BERTScore behavior from token-overlap F1 and cover empty-input handling.

## Capabilities

### New Capabilities
- `evaluation-metrics`: Defines correctness requirements for automatic evaluation metrics, including real BERTScore semantics for referenced text outputs.

### Modified Capabilities

## Impact

- Affected code: `backend/app/evaluation/metrics.py`, `backend/app/evaluation/report.py`, backend dependency metadata and evaluation tests.
- Dependencies: adds a real BERTScore implementation and any required model/runtime packages to the backend environment.
- Systems: offline evaluation runs may require model assets to be installed or cached; missing dependencies should produce an explicit error instead of silently reporting token overlap as BERTScore.
