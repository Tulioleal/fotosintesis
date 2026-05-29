## 1. Test Fixtures

- [x] 1.1 Import or define the minimal evaluation dataset models needed by the tests in `backend/tests/test_evaluation_pipeline.py`.
- [x] 1.2 Add a small fake judge provider that returns a failed judge result with stable failure reasons.

## 2. Failure Coverage

- [x] 2.1 Add a runner test for a failed judge result that asserts `passed == False`, failure reasons are present, and persisted `result.json` records the same failed state.
- [x] 2.2 Add a runner test for a failed tool action claimed as successful that asserts `passed == False`, `failed_action_claim_rate > 0`, and the failure reason is recorded.

## 3. Verification

- [x] 3.1 Run the targeted backend evaluation tests.
- [x] 3.2 Run the relevant backend test suite if the targeted tests pass.
