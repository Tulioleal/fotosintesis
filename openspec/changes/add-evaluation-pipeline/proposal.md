## Why

The MVP must be evaluated across retrieval, generation, tools, plant identification and end-to-end flows to avoid shipping an unmeasured AI experience. This change creates the evaluation dataset, runner, metrics and report.

## What Changes

- Create initial evaluation dataset format and seed 50 cases distributed by target flows.
- Implement evaluation runner for assistant RAG, plant profile generation, revive plant, incremental knowledge, reminders agent, light measurement context and plant identification MaaS.
- Calculate retrieval recall and precision metrics.
- Calculate BERTScore and ROUGE-L for applicable text outputs.
- Implement LLM-as-a-judge rubric.
- Calculate tool success, unnecessary web search and failed action claim rates.
- Calculate visual identification metrics.
- Persist evaluation runs, scores, failures and per-flow summaries.
- Generate final evaluation report.

## Capabilities

### New Capabilities

- `evaluation-pipeline`: dataset, runner, metrics, judge rubric, persistence and report generation.

### Modified Capabilities

- None.

## Impact

- Affects evaluation data formats, backend evaluation services, metrics persistence, provider judge integration and project documentation.
