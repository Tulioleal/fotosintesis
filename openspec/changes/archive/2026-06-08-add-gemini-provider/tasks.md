## 1. Configuration And Dependencies

- [x] 1.1 Add `GEMINI_API_KEY`, `GEMINI_TEXT_MODEL`, `GEMINI_VISION_MODEL` and `GEMINI_JUDGE_MODEL` backend settings with mock-preserving defaults and Flash-class model defaults verified during implementation.
- [x] 1.2 Add the official `google-genai` Python SDK to backend project dependencies.
- [x] 1.3 Update backend environment examples and deployment configuration examples with Gemini provider selectors, credential and role-specific model settings.

## 2. Gemini Provider Implementation

- [x] 2.1 Add `backend/app/providers/gemini.py` with `GeminiProviderError` and Gemini client construction isolated from domain code.
- [x] 2.2 Implement `GeminiModelProvider.generate_text()` and map responses into `TextGenerationResult`.
- [x] 2.3 Implement strict `GeminiModelProvider.generate_json()` using the supplied schema when supported, returning only parsed JSON objects in `JsonGenerationResult`.
- [x] 2.4 Implement `GeminiVisionProvider.analyze_image()` for plant identification and map structured responses into `ImageAnalysisResult` and `PlantCandidate` values.
- [x] 2.5 Implement `GeminiJudgeProvider.judge_response()` and map score, pass status and reasons into `JudgeResult`.
- [x] 2.6 Wrap Gemini model, vision and judge SDK calls with the existing provider-call observability helper using sanitized metadata.
- [x] 2.7 Normalize SDK import failures, SDK call failures and invalid response parsing failures as `GeminiProviderError`.

## 3. Provider Registry Wiring

- [x] 3.1 Import Gemini providers in the provider factory.
- [x] 3.2 Support `MODEL_PROVIDER=gemini` using `GEMINI_API_KEY` and `GEMINI_TEXT_MODEL`.
- [x] 3.3 Support `VISION_PROVIDER=gemini` using `GEMINI_API_KEY` and `GEMINI_VISION_MODEL`.
- [x] 3.4 Support `JUDGE_PROVIDER=gemini` using `GEMINI_API_KEY` and `GEMINI_JUDGE_MODEL`.
- [x] 3.5 Ensure Gemini credentials are required only for selected Gemini roles and not for mock, OpenAI, search or embedding roles.
- [x] 3.6 Keep Gemini unsupported for search and embedding provider builders in this change.

## 4. Tests

- [x] 4.1 Add deterministic fake Gemini SDK tests for text generation response mapping.
- [x] 4.2 Add deterministic fake Gemini SDK tests for strict JSON generation success and invalid or non-object JSON failures.
- [x] 4.3 Add deterministic fake Gemini SDK tests for plant vision candidate response mapping.
- [x] 4.4 Add deterministic fake Gemini SDK tests for judge response mapping.
- [x] 4.5 Add factory tests proving Gemini model, vision and judge roles can be selected independently.
- [x] 4.6 Add factory tests proving selected Gemini roles require `GEMINI_API_KEY` while unselected roles do not.
- [x] 4.7 Add tests proving Gemini model selection does not change configured search or embedding providers.
- [x] 4.8 Add tests proving Gemini vision selection does not change configured model provider.
- [x] 4.9 Add tests proving Gemini judge selection does not change runtime generation provider wiring.
- [x] 4.10 Add tests proving default local and CI configuration still uses deterministic mocks without Gemini credentials.
- [x] 4.11 Add tests proving Gemini provider calls use existing provider-call observability wrapping.

## 5. Verification

- [x] 5.1 Run backend provider and system provider tests relevant to Gemini wiring.
- [x] 5.2 Run the backend test suite or the narrowest reliable equivalent if full suite dependencies are unavailable.
- [x] 5.3 Confirm `openspec status --change add-gemini-provider` reports the change as apply-ready during implementation handoff.
