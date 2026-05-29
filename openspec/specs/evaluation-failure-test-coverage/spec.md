## Purpose

Define regression-test coverage requirements for evaluation failure handling.

## Requirements

### Requirement: Judge failures are regression tested
The backend test suite SHALL include a focused evaluation-runner test that exercises a failed judge result and verifies the case is marked as failed with the judge failure reasons preserved.

#### Scenario: Failed judge result marks case failed
- **WHEN** an evaluation case is run with a judge provider returning `passed == False` and one or more reasons
- **THEN** the resulting case SHALL have `passed == False` and include the judge reasons in its failures
- **AND** the persisted run result SHALL record the same failed state and failure reasons

### Requirement: Failed tool success claims are regression tested
The backend test suite SHALL include a focused evaluation test that exercises a tool trace where the action failed but was claimed as successful, and verifies the metric violation is recorded.

#### Scenario: Failed action claimed as complete records violation
- **WHEN** an evaluation case includes a tool trace with `success == False` and `claimed_success == True`
- **THEN** the resulting case SHALL have `passed == False`
- **AND** the case scores SHALL include a `failed_action_claim_rate` greater than zero
- **AND** the case failures SHALL include a reason indicating that a failed tool action was claimed as completed
