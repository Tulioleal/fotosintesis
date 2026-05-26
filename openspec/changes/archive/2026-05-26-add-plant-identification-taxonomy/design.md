## Context

This slice turns image input into validated, user-confirmed plant candidates. It depends on provider interfaces and object storage but should not generate full plant profiles or save garden records beyond exposing confirmed candidate data for later slices.

## Goals / Non-Goals

**Goals:**

- Capture or upload plant images with graceful permission fallbacks.
- Store image metadata and files safely.
- Return up to three possible MaaS candidates with transparent uncertainty.
- Validate and normalize scientific names with GBIF.
- Prevent downstream definitive actions until validation and user confirmation happen.

**Non-Goals:**

- No dedicated botanical API dependency beyond GBIF validation.
- No final profile generation, RAG enrichment, reminders or garden persistence.

## Decisions

- Candidate confidence is qualitative, not presented as a calibrated botanical probability.
- GBIF validates names and synonyms; it does not identify from images.
- The UI must communicate possible matches and provide retry/manual search paths.
- Failed or unvalidated candidates cannot create definitive records.

## Risks / Trade-offs

- MaaS may produce plausible but incorrect names; confirmation and GBIF normalization reduce but do not eliminate risk.
- GBIF may fail on aliases or incomplete names; the flow needs manual search and no-match recovery.
