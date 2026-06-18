## 1. Web Fallback Diagnostics

- [x] 1.1 Add structured logging around web fallback query construction, including trace ID, confirmed taxonomy, topic, required or missing aspects, and generated query.
- [x] 1.2 Add structured logging for selected search candidates, including URL, domain, trust status, snippet length, and whether the candidate is reused or newly searched.
- [x] 1.3 Add operationally visible page evidence fetch/extraction logs with sanitized URL or URL hash, domain, fetch status, error category, content length, and timing.
- [x] 1.4 Add logging for evidence passed to the combined judge, including evidence type, fetched-content count, snippet-only count, total evidence chars, and source count.

## 2. Evidence Quality And Extraction

- [x] 2.1 Extend `TrustedPageEvidence` metadata so callers can distinguish fetched content from snippet-only evidence and fetch failures.
- [x] 2.2 Improve or replace the current page readable-text extraction path while preserving HTTPS-only, trusted-domain, redirect, byte-size, timeout, and content-type controls.
- [x] 2.3 Update `_usable_web_results` and web fallback evidence selection so snippet-only results are weak candidates unless they directly cover at least one requested aspect.
- [x] 2.4 Ensure combined judge evidence prefers fetched trusted page content and marks snippet-only evidence in metadata when used.

## 3. Search Reuse And Source Selection

- [x] 3.1 Extend knowledge acquisition results to expose same-request search candidates or fetched evidence metadata when acquisition performs provider search.
- [x] 3.2 Update assistant retrieval/fallback state to carry reusable search candidates without persisting unvalidated evidence.
- [x] 3.3 Update web fallback to reuse same-request candidates before issuing a new search provider call when taxonomy and requested aspects match.
- [x] 3.4 Add or prioritize care-oriented trusted source domains while preserving trust validation and fetch limits.
- [x] 3.5 Keep existing web query construction strategy unchanged; do not add per-aspect query expansion in this change.

## 4. Web Validation Behavior

- [x] 4.1 Change combined web evidence validation so low confidence alone does not downgrade direct non-safety source-supported web evidence to insufficient.
- [x] 4.2 Preserve strict validation for safety-sensitive web aspects such as pet toxicity and human edibility.
- [x] 4.3 Keep confidence in answerability metadata, source metadata, diagnostics, and persisted validated web claims where applicable.
- [x] 4.4 Ensure contradictory or missing direct source support still prevents source-backed definitive answers.

## 5. Provider Metadata

- [x] 5.1 Ensure Gemini search result normalization preserves title, URL, source domain, snippet, and available snippet provenance metadata.
- [x] 5.2 Ensure Gemini search remains a grounded URL provider and does not perform page fetching inside the provider layer.
- [x] 5.3 Update provider tests for duplicate citations, support-text snippets, and title-only fallback snippets.

## 6. Tests And Verification

- [x] 6.1 Add tests for fetch failure producing snippet-only weak candidates that do not become strong usable evidence without direct aspect coverage.
- [x] 6.2 Add tests for fetched page content supporting requested aspects and being passed to the combined judge.
- [x] 6.3 Add tests proving low-confidence direct non-safety web evidence is not blocked solely by the general validation threshold.
- [x] 6.4 Add tests proving safety-sensitive web evidence still requires strict validation.
- [x] 6.5 Add tests proving acquisition search candidates can be reused and duplicate search provider calls are avoided.
- [x] 6.6 Add tests for web fallback diagnostic log fields without exposing secrets.
- [x] 6.7 Run focused assistant, knowledge acquisition, page evidence, and search provider tests.
- [x] 6.8 Run broader backend tests if focused tests pass.
