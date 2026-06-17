## Context

The assistant graph classifies each chat message before retrieval. The current classifier contract is enforced by Pydantic after a provider JSON-generation call, but the Gemini response schema does not explicitly require every field that Pydantic requires. As a result, recoverable structured-output omissions such as a missing `confidence` field immediately trigger deterministic routing and produce noisy `tool_failures` even when the model likely selected the correct intent.

The existing assistant-agent spec also treats low classifier confidence as a hard rejection condition. That makes the model's self-estimated confidence act like a calibrated probability, which it is not. The new behavior should retain structured validation but make deterministic routing a narrower fallback for unavailable or unusable classifier output.

## Goals / Non-Goals

**Goals:**
- Require all classifier contract fields at the provider schema level, especially `confidence`.
- Retry once for recoverable classifier output validation failures before deterministic fallback.
- Accept structurally valid LLM classifications even when their confidence is below the configured threshold.
- Preserve classifier confidence in logs and diagnostics as an observability signal.
- Keep deterministic fallback for provider failures, timeouts, non-object responses, invalid JSON, invalid enum values, forbidden extra fields, and invalid output after retry.

**Non-Goals:**
- Removing deterministic classification entirely.
- Treating classifier confidence as a calibrated probability.
- Changing public chat request or response schemas.
- Changing answerability judge thresholds or RAG evidence validation policy.
- Adding new providers or external dependencies.

## Decisions

1. Make the JSON schema the first line of enforcement.

   The classifier schema will include a top-level `required` list matching the `CareClassification` contract. This makes provider structured output less likely to omit fields before Pydantic validation runs. Alternative considered: only changing the prompt. Prompt-only enforcement is weaker because structured output providers can still omit non-required fields.

2. Keep Pydantic validation authoritative.

   The provider schema guides generation, but `CareClassification.model_validate()` remains the source of truth for valid classifier data. This keeps enum validation, extra-field rejection, and numeric bounds in one domain contract. Alternative considered: trusting provider schema output directly. That would weaken domain validation and could let provider-specific quirks affect routing.

3. Retry once for recoverable structured-output failures.

   When the first classifier response is non-object data or fails Pydantic validation, the graph will issue one repair-style classifier call with stricter instructions. If the retry fails, deterministic fallback remains the safe path. Alternative considered: retrying multiple times. More retries increase latency and cost for a pre-retrieval step.

4. Low confidence is diagnostic-only.

   A valid LLM classification with confidence below `assistant_classification_accept_threshold` will be used for routing while logging the low-confidence condition. This avoids discarding valid model output based on a self-estimated number. Alternative considered: lowering the threshold. That still treats confidence as a hard gate and only reduces, rather than removes, the failure mode.

5. Tool failures should represent actual failures.

   Low confidence will not be appended to `tool_failures`. Recoverable first-attempt validation errors may be retained in diagnostic context only if useful, but successful retry should not cause the final service warning to imply a failed request. Alternative considered: preserving every classifier anomaly in `tool_failures`. That keeps observability but makes successful repair paths look operationally broken.

## Risks / Trade-offs

- [Risk] Accepting low-confidence valid classifications could allow an uncertain model route to drive retrieval. -> Mitigation: keep closed enums, required aspects, schema validation, confirmed taxonomy gates, evidence validation, and answerability judging downstream.
- [Risk] A retry adds latency when the provider returns invalid classifier output. -> Mitigation: retry only once and only for recoverable validation failures, not for timeouts or provider exceptions.
- [Risk] Gemini may still omit fields despite a stricter schema. -> Mitigation: use explicit `required`, field descriptions, prompt reinforcement, and one repair retry before deterministic fallback.
- [Risk] Existing monitoring may rely on `tool_failures` for classifier anomalies. -> Mitigation: continue structured classifier logging with source, confidence, and fallback reason while avoiding failure metadata for accepted classifications.
