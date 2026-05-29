## 1. Dependency and Metric Implementation

- [x] 1.1 Add the real BERTScore package and required runtime dependencies to `backend/pyproject.toml`.
- [x] 1.2 Replace the token-overlap `bertscore` implementation in `backend/app/evaluation/metrics.py` with a model-backed BERTScore call.
- [x] 1.3 Preserve the existing `precision`, `recall` and `f1` return keys as floats.
- [x] 1.4 Keep empty reference or empty candidate inputs returning zero-valued BERTScore fields without invoking the model.
- [x] 1.5 Ensure dependency or model initialization failures raise an explicit evaluation error and do not fall back to token-overlap scoring.

## 2. Report Updates

- [x] 2.1 Update `backend/app/evaluation/report.py` metrics text to describe real BERTScore for referenced text outputs.
- [x] 2.2 Remove report limitation wording that describes BERTScore as token-overlap, dependency-free or only BERTScore-compatible.

## 3. Tests and Verification

- [x] 3.1 Add backend tests for empty-input BERTScore behavior.
- [x] 3.2 Add backend tests that verify the wrapper delegates non-empty inputs to the model-backed BERTScore implementation and returns float fields.
- [x] 3.3 Add backend tests proving dependency/model failures do not return token-overlap scores.
- [x] 3.4 Add or update report tests to verify generated report wording describes real BERTScore accurately.
- [x] 3.5 Run backend lint and test commands relevant to evaluation metrics.
