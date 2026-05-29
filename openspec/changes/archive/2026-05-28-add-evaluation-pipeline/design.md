## Context

This slice creates an evaluation framework that can be used before and after feature slices mature. It should support mocks and deterministic cases where real providers are unavailable.

## Goals / Non-Goals

**Goals:**

- Seed an initial 50-case dataset across target MVP flows.
- Measure retrieval, generation, judge quality, agent/tool behavior and visual identification.
- Persist runs and failures for regression analysis.
- Produce a final report with protocol, metrics, prompts, results, failures, limitations and conclusions.

**Non-Goals:**

- No claim that automatic metrics fully prove botanical correctness.
- No production monitoring replacement; this is offline/controlled evaluation.

## Decisions

- Retrieval metrics include `retrieval_recall@5` and `precision@5`.
- Text metrics include BERTScore and ROUGE-L where references exist.
- Judge rubric covers grounding, botanical correctness, usefulness, clarity, safety, uncertainty and tool use.
- Tool metrics include success rate, unnecessary web search rate and failed action claim rate.
- Visual metrics include top 1 accuracy, top 3 accuracy, taxonomy validation rate and low confidence detection rate.

## Risks / Trade-offs

- LLM-as-a-judge can be biased; use a provider ideally distinct from the generator and preserve prompts/results.
- Initial dataset coverage may be thin; failures should drive future case additions.
