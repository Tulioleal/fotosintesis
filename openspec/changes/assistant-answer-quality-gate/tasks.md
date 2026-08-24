## 1. Profile and Gate Arithmetic

- [ ] 1.1 Reject `0.0` threshold values at profile load with an explicit configuration error.
- [ ] 1.2 Add a named `quality_gate` profile with non-zero judge, aggregate, and contributor thresholds (judge aggregate pass rate target 0.60).
- [ ] 1.3 Redefine aggregate approval to compute the pass rate over supported cases only.
- [ ] 1.4 Add a supported-case-ratio floor; fail the run with an explicit reason when below it.
- [ ] 1.5 Extend tests: gate arithmetic, denominator exclusion of unsupported cases, floor failure.

## 2. Artifacts and Reporting

- [ ] 2.1 Write `runs/<run_id>/report.md` and `result.json` including mode, recording version, profile, counts, per-threshold failures.
- [ ] 2.2 Bound retained runs to latest N; prune older directories.
- [ ] 2.3 Print structured gate summary; exit non-zero on gate failure.

## 3. CI Enforcement

- [ ] 3.1 Add backend CI job running `backend/scripts/run_evaluation.py --mode recorded` against the committed recording set.
- [ ] 3.2 Fail build when not approved, errored, or below the supported-case floor.

## 4. Docs

- [ ] 4.1 Replace the `python -m app.evaluation.runner` instruction in `DOCS/local-docker-compose.md` with `python scripts/run_evaluation.py`.
- [ ] 4.2 Document gate definition, profile selection, artifact locations, recording refresh.

## 5. Verification

- [ ] 5.1 Run recorded gate locally; confirm artifacts, exit codes, failure enumeration.
- [ ] 5.2 Prove a degraded answer fails the gate and a clean replay passes deterministically twice.
- [ ] 5.3 Backend lint/typecheck/test suites green.
