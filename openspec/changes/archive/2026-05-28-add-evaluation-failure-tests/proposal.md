## Why

Evaluation failure behavior is implemented, but key failure scenarios are not directly covered by tests. Adding focused coverage reduces the risk of regressions where failed judge outcomes or failed tool actions are incorrectly recorded as successful.

## What Changes

- Add backend tests for judge failure handling in the evaluation runner.
- Add backend tests for tool-failure-claimed-as-success detection in evaluation metrics.
- Assert both boolean pass/fail outcomes and persisted failure or violation details.
- No runtime behavior or API changes are intended.

## Capabilities

### New Capabilities
- `evaluation-failure-test-coverage`: Covers regression-test expectations for evaluation judge failures and failed action success-claim violations.

### Modified Capabilities

## Impact

- Affected code: backend evaluation tests, with assertions against `backend/app/evaluation/runner.py` and `backend/app/evaluation/metrics.py` behavior.
- APIs: none.
- Dependencies: none expected.
- Systems: backend test suite only.
