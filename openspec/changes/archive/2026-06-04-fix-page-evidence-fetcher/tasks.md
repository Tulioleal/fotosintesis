## 1. Fetcher Bug Fix

- [x] 1.1 Update `backend/app/knowledge/page_evidence.py` so `TrustedPageEvidenceFetcher.__init__()` assigns `self.max_redirects = max_redirects`.
- [x] 1.2 Keep existing trusted source validation, redirect handling, content-type limits, response-size limits and extraction behavior unchanged.
- [x] 1.3 If existing logging patterns support it, add non-user-facing debug metadata for trusted page fetch failures without logging fetched page content or secrets.

## 2. Fetcher Regression And Safety Tests

- [x] 2.1 Add a focused regression test that instantiates `TrustedPageEvidenceFetcher` and exercises `fetch()` or `_fetch_sync()` through a controlled fake so the real fetch path no longer raises `AttributeError: max_redirects`.
- [x] 2.2 Add a test proving non-HTTPS URLs are rejected before any network fetch is opened.
- [x] 2.3 Add a test proving untrusted URLs are not fetched.
- [x] 2.4 Add a test proving unsupported content types return degraded snippet fallback evidence.
- [x] 2.5 Add a test proving oversized responses return degraded snippet fallback evidence.
- [x] 2.6 Add a test proving redirects crossing outside trusted sources are rejected and return degraded snippet fallback evidence.

## 3. Assistant Fallback Answer Tests

- [x] 3.1 Add a successful fetched-content fallback-answer test that provides `TrustedPageEvidence.content` and asserts the assistant answer includes extracted content.
- [x] 3.2 In the same successful fallback test, assert the answer is not only the original citation or snippet markdown.
- [x] 3.3 Add a fetch-failure degradation test that simulates page fetch failure and asserts the assistant still answers using the trusted snippet.
- [x] 3.4 In the fetch-failure degradation test, assert no exception blocks the response.

## 4. Manual Verification

- [x] 4.1 Run a small local reproduction with the originally reported three URLs and confirm fetches no longer fail because of `max_redirects`.
- [x] 4.2 Inspect the extracted evidence for those URLs and note whether it is actual page text or mostly site boilerplate.
- [x] 4.3 Confirm no trusted domains or source-selection behavior were changed.

## 5. Automated Verification

- [x] 5.1 From `backend/`, run `MODEL_PROVIDER=mock VISION_PROVIDER=mock JUDGE_PROVIDER=mock SEARCH_PROVIDER=mock EMBEDDING_PROVIDER=mock pytest tests/test_assistant_agent.py tests/test_knowledge_rag.py`.
- [x] 5.2 From `backend/`, run `ruff check app/knowledge/page_evidence.py app/assistant/tools.py app/assistant/graph.py tests/test_assistant_agent.py`.
- [x] 5.3 Re-run `/opsx-verify` before archiving.

## 6. OpenSpec State

- [x] 6.1 Treat this as a post-verification bug fix for previously completed implementation work unless the active workflow requires adding a follow-up implementation task.
- [x] 6.2 Archive only after the bug fix, tests, manual verification and `/opsx-verify` pass.
