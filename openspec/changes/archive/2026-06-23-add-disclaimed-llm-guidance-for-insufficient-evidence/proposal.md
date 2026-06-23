## Why

Plant-care answers currently become overly conservative when answerability judging marks otherwise relevant RAG or combined RAG plus web evidence as insufficient. This wastes useful validated context and produces generic fallback responses where a transparent, bounded, non-validated guidance section would better help users without weakening evidence quality.

## What Changes

- Add a runtime-only disclaimed general-guidance answer mode for non-safety-sensitive plant-care questions when relevant evidence or confirmed plant context exists but validated evidence is incomplete or insufficient.
- Require final answers in this mode to separate validated source-supported facts from general model guidance, state what was and was not validated, and ask for missing details such as photos, location, symptoms, or context when useful.
- Keep full answerability behavior unchanged: fully validated evidence still produces the current grounded answer path.
- Keep partial answer behavior grounded for supported aspects while clearly labeling limitations and any general guidance for unsupported non-critical aspects.
- Keep safety-sensitive topics conservative unless the specific safety claims are directly source-supported, including toxicity, edibility, pets, children, medical-like exposure, chemical dosing, severe disease diagnosis, and pesticide instructions.
- Expose diagnostics indicating when runtime-only general guidance was used.
- Preserve strict ingestion policy: only validated `source_support` claims may be emitted as ingestion candidates or persisted; unvalidated general guidance is never treated as source support, never cited, and never written to RAG.

## Capabilities

### New Capabilities

### Modified Capabilities

- `assistant-agent`: Add the disclaimed general-guidance answer branch, safety gating, user-facing transparency requirements, and diagnostic metadata for non-validated runtime guidance.
- `knowledge-rag-acquisition`: Clarify that disclaimed model guidance generated for insufficient evidence remains runtime-only and cannot be included in validated claim payloads, source support, or persistent knowledge.

## Impact

- Affected backend code includes assistant answer generation, fallback routing after answerability judging, prompt construction, response diagnostics, and tests around insufficient evidence.
- No database schema or dependency changes are expected.
- Existing strict answerability judging and validated-claim extraction remain authoritative for RAG persistence and ingestion payloads.
