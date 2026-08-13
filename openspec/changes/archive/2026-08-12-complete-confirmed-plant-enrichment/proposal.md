## Why

Confirmed-plant enrichment has durable scheduling and strong component coverage, but its production orchestration is not proven end to end and two acceptance/convergence defects can prevent semantically supported evidence from becoming retrievable. Completing these gaps is necessary before enrichment efficacy can be measured or the feature can be considered production-complete.

## What Changes

- Make semantic source-support binding provenance-safe without using exact quote substring matching as evidence-coverage authority.
- Refresh relational and vector aspect metadata when unchanged evidence gains newly accepted aspect support, preserving one content, chunk, embedding, and vector identity.
- Add production PostgreSQL + pgvector verification from confirmation and worker execution through missing-aspect acquisition, persistence, indexing, and later retrieval.
- Add a deterministic enrichment efficacy evaluation covering empty, sparse, complete, contradictory, multilingual, safety-sensitive, retry, policy-change, and source-change cases.
- Record bounded acquisition efficacy metrics for local coverage, final coverage gain, accepted aspects, acquisition outcome, search count, completion time, and later retrieval verification without exposing claims, quotes, source bodies, or taxonomy text as labels.
- Make worker readiness available before expensive production-handler dependency construction and avoid global handler registration when an explicit registry is supplied.
- Make lease-loss verification depend on durable state and bounded events rather than transient private execution-map timing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `confirmed-plant-enrichment`: Complete semantic source binding, vector aspect convergence, measurable efficacy, and production end-to-end verification requirements.
- `knowledge-rag-acquisition`: Require accepted enrichment aspect support to converge into retrieval metadata without lexical semantic gates.
- `durable-background-jobs`: Require prompt readiness-listener availability during dependency validation and durable lease-loss observability independent of transient in-memory execution state.

## Impact

- Affects semantic coverage normalization, enrichment claim selection and persistence, vector-node metadata upsert, production enrichment orchestration tests, and worker startup/lease-loss observability.
- Adds bounded metrics and deterministic evaluation fixtures; no public API breaking change is expected.
- Requires PostgreSQL 16 + pgvector integration coverage with mock search, judge, fetch, and embedding providers.
- Updates existing OpenSpec requirements and replaces unsupported completed-task claims with executable end-to-end evidence.
