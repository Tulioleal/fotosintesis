---
description: Run or capture an OpenSpec verification and save the result as a versioned report
---

Save the result of an OpenSpec task verification as a versioned markdown report.

**Input**: Optionally specify a spec or change name after `/opsx-save-verification` (e.g., `/opsx-save-verification add-auth`). If omitted, use the spec or change being verified in the current conversation. If no target can be identified, prompt the user to select one from the available OpenSpec changes. Do not guess when multiple targets are possible.

**Steps**

1. **Identify the spec**

   Resolve the target spec or change name. Use the canonical name exactly as the OpenSpec directory or change identifier, preserving hyphens. Call this `<spec-name>` for the rest of the command.

2. **Obtain the verification result**

   If a verification result for `<spec-name>` already exists in the current conversation, use that result.

   Otherwise, perform the same verification workflow used to verify an OpenSpec change:
   - Run `openspec status --change "<spec-name>" --json`.
   - Run `openspec instructions apply --change "<spec-name>" --json` and read every artifact listed in `contextFiles`.
   - Check task completion, spec coverage, correctness, scenario coverage, design adherence, and code-pattern coherence where the corresponding artifacts exist.
   - Generate a complete markdown verification report with a summary scorecard, grouped CRITICAL/WARNING/SUGGESTION issues, actionable recommendations, and a final assessment.

3. **Determine the next version**

   The output directory is `opsx-verifications/<spec-name>/` at the project root. Create it if it does not exist.

   Inspect existing files matching `opsx-verifications/<spec-name>/*.verification.md`. Extract the numeric version from filenames matching:

   ```text
   <spec-name>-<version>-YYYY-MM-DD.verification.md
   ```

   Use `1` when no matching reports exist. Otherwise use one greater than the highest existing version. Never overwrite an existing report.

4. **Write the report**

   Use the current date in `YYYY-MM-DD` format. Save the complete verification result to:

   ```text
   opsx-verifications/<spec-name>/<spec-name>-<version>-<date>.verification.md
   ```

   The report must retain the verification content and include the target spec/change name, verification date, and version. Do not modify the existing OpenSpec command or verification skill.

5. **Display the result**

   Report the exact path of the saved file and its version. If the target directory or report already exists, choose the next available version rather than overwriting any file.

**Output Format**

The saved file must be clear markdown and preserve:

- Verification target and date
- Summary scorecard
- Completeness findings
- Correctness findings
- Coherence findings
- CRITICAL, WARNING, and SUGGESTION issues
- Final assessment

If a verification dimension was skipped because its artifact was unavailable, record that reason in the report.
