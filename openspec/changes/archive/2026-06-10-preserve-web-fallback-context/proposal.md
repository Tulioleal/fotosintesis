## Why

Trusted web fallback currently loses important intent context for unsupported botanical questions by searching on a reduced generic topic such as `care`. When trusted web search fails, the response also records the tool failure but drops the `web_search_used` fallback reason, making diagnostics incomplete.

## What Changes

- Build trusted web fallback queries from the plant scientific name plus a capped copy of the original user question and trusted botanical source terms.
- Preserve unsupported-question terms such as pet-safety or native-range wording in the trusted web search query.
- Preserve the `web_search_used` fallback reason when trusted web search fails before returning usable results.
- Extend assistant-agent tests to assert query context preservation and fallback reason preservation on search failure.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `assistant-agent`: Trusted web fallback query construction and failure metadata behavior are refined for insufficient botanical evidence.

## Impact

- Affected backend code: `backend/app/assistant/graph.py`.
- Affected tests: `backend/tests/test_assistant_agent.py`.
- No API, database, dependency, or frontend changes are expected.
