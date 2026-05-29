## Context

The backend evaluation module currently computes ROUGE-L locally and exposes a `bertscore` function that returns `precision`, `recall` and `f1`. Despite the name, that function uses token multiset overlap, and the generated report documents it as "BERTScore-compatible token F1". Evaluation consumers need the BERTScore label to mean model-based semantic similarity, not lexical overlap.

The backend uses `pyproject.toml` for dependencies and pytest for test coverage. Evaluation is an offline path, so adding a heavier model-backed metric is acceptable, but missing model/runtime dependencies must be visible rather than silently falling back to the old approximation.

## Goals / Non-Goals

**Goals:**
- Compute referenced text BERTScore with a real BERTScore implementation that returns precision, recall and F1.
- Keep the existing public metric shape so evaluation result serialization and report consumers do not need schema changes.
- Make model/dependency failures explicit and actionable.
- Update report wording to describe the metric accurately.
- Add tests that prevent a token-overlap implementation from being reintroduced under the BERTScore name.

**Non-Goals:**
- Replace ROUGE-L, retrieval, tool or visual evaluation metrics.
- Introduce provider-backed LLM judging changes.
- Add online model download orchestration beyond normal dependency/model-cache behavior.
- Change evaluation result storage schema.

## Decisions

- Use the published Python `bert-score` package for metric computation instead of implementing embedding similarity directly. This avoids maintaining model tokenization, contextual embedding extraction and IDF/scoring details in application code.
- Configure BERTScore through a single backend helper with fixed defaults for language/model behavior. Centralizing the call keeps the output shape stable and makes future model changes localized.
- Preserve the existing `bertscore(reference, candidate) -> dict[str, float]` interface. Existing evaluation callers can continue consuming `precision`, `recall` and `f1` without migration.
- Return zero scores for empty reference or candidate inputs before invoking the model. Empty strings are not semantically comparable and this preserves current edge-case behavior.
- Do not fall back to token-overlap when the BERTScore dependency or model runtime is unavailable. The evaluation should fail with a clear error because approximate lexical overlap under the BERTScore name is the problem being fixed.

## Risks / Trade-offs

- Increased install and runtime cost -> Limit the dependency to the backend environment and keep the API surface isolated to evaluation code.
- Model assets may not be cached in offline environments -> Surface a clear dependency/model initialization error so CI or operators can preinstall/cache the required assets.
- Floating point values can vary slightly across model/runtime versions -> Use tolerance-based tests and avoid exact score assertions except for empty-input behavior.
- Semantic-score tests can become slow -> Keep direct tests focused on wrapper behavior and use monkeypatching where possible to verify integration and fallback prevention.

## Migration Plan

1. Add the real BERTScore dependency to backend project metadata.
2. Replace token-overlap logic in `backend/app/evaluation/metrics.py` with the package-backed implementation while preserving return keys.
3. Update report protocol and limitations text to describe real BERTScore and remove dependency-free approximation language.
4. Add or update backend tests for empty inputs, integration call shape and no lexical fallback behavior.
5. Run backend lint and tests.

Rollback is limited to reverting the dependency and metric implementation changes. If rollback is required, report wording must also be reverted or changed to avoid claiming real BERTScore.

## Open Questions

- Which exact BERTScore model should be pinned for the project default if the package default is not acceptable for the target language mix?
