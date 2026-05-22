## 1. Evaluation Pipeline

- [ ] 1.1 Create initial evaluation dataset format and seed 50 cases distributed by target flows
- [ ] 1.2 Implement evaluation runner for assistant_rag, plant_profile_generation, revive_plant, incremental_knowledge, reminders_agent, light_measurement_context and plant_identification_maas
- [ ] 1.3 Calculate retrieval_recall@5 and precision@5
- [ ] 1.4 Calculate BERTScore and ROUGE-L for applicable text outputs
- [ ] 1.5 Implement LLM-as-a-judge rubric for grounding, botanical correctness, usefulness, clarity, safety, uncertainty handling and tool use
- [ ] 1.6 Calculate tool_success_rate, unnecessary_web_search_rate and failed_action_claim_rate
- [ ] 1.7 Calculate visual identification metrics including top_1_accuracy, top_3_accuracy, taxonomy_validation_rate and low_confidence_detection_rate
- [ ] 1.8 Persist evaluation runs, scores, failures and per-flow summaries
- [ ] 1.9 Generate final evaluation report with protocol, metrics, prompts, results, failures, limitations and conclusions
