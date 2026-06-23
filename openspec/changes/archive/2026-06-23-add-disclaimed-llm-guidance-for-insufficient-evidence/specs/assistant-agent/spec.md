## ADDED Requirements

### Requirement: Disclaimed general guidance answer mode
The assistant SHALL support a runtime-only `general_guidance_with_disclaimer` answer mode for plant-care questions when validated evidence is relevant but incomplete or insufficient and the missing guidance is not safety-sensitive. This mode MUST preserve the classified `answer_language`, MUST clearly separate source-validated facts from general model guidance, MUST explicitly state which requested information was not validated by retrieved sources, MUST NOT cite general guidance as evidence, and MUST request additional details when they would materially improve the answer.

#### Scenario: Full evidence keeps grounded answer behavior
- **WHEN** answerability validation returns full coverage for all requested required aspects with valid source support and no contradictions
- **THEN** the assistant uses the existing grounded answer behavior
- **AND** the assistant does not label the answer as runtime-only general guidance

#### Scenario: Partial non-safety evidence includes limitations and optional guidance
- **WHEN** answerability validation returns source-supported coverage for at least one requested non-safety aspect but leaves other non-safety aspects missing
- **THEN** the assistant answers the validated source-supported parts with any applicable citations
- **AND** the assistant states which requested aspects were not validated by the available sources
- **AND** any guidance for missing aspects is clearly labeled as general guidance that was not validated by the retrieved sources

#### Scenario: Insufficient non-safety evidence with relevant context provides disclaimed guidance
- **WHEN** answerability validation returns `status: "insufficient"` for a plant-care question
- **AND** the assistant has relevant retrieved evidence, web evidence, validated plant context, or confirmed taxonomy for the request
- **AND** no missing requested aspect is safety-sensitive
- **THEN** the assistant may generate a `general_guidance_with_disclaimer` answer instead of a generic insufficient-evidence fallback
- **AND** the answer states that the retrieved sources did not validate the requested answer
- **AND** the answer presents any general guidance in a clearly labeled non-validated section
- **AND** the answer asks for a close photo, symptoms, location, treatment history, or other missing details when useful

#### Scenario: Pest question receives cautious non-validated guidance
- **WHEN** a user asks about small white insects under leaves
- **AND** retrieved evidence or combined evidence does not validate the exact pest identity or a treatment for the specific plant
- **AND** the requested aspects are limited to non-safety pest identification, inspection, isolation, or non-destructive care actions
- **THEN** the assistant states that the sources did not confirm the insect identity or validate a specific treatment
- **AND** the assistant may provide general, non-validated guidance such as isolating the plant, inspecting leaf undersides, removing visible insects with water or a damp cloth, and requesting a close photo
- **AND** the assistant does not recommend insecticides unless the claim is directly source-supported and includes appropriate label or expert-use constraints

#### Scenario: No relevant plant context keeps clarification behavior
- **WHEN** answerability validation returns insufficient evidence
- **AND** the assistant has no relevant plant context, no confirmed taxonomy, no relevant retrieved evidence, and no useful source-supported facts
- **THEN** the assistant uses the existing clarification or insufficient-evidence fallback behavior
- **AND** the assistant does not invent plant-specific guidance

#### Scenario: Safety-sensitive missing aspects remain conservative
- **WHEN** a requested aspect involves toxicity, edibility, pets, children, medical-like exposure, chemical dosing, severe disease diagnosis, pesticide instructions, or another safety-sensitive care boundary
- **AND** direct source-supported evidence does not validate the specific safety claim at the configured safety threshold
- **THEN** the assistant does not use general model knowledge to claim safety, toxicity, edibility, exposure outcomes, dosing, diagnosis certainty, or pesticide instructions
- **AND** the assistant uses the existing conservative safety fallback or answers only directly source-supported safety facts

### Requirement: General guidance diagnostics
The assistant response diagnostics SHALL expose whether runtime-only general model guidance was used. The diagnostic flag MUST be bounded metadata, MUST NOT expose prompts, raw model reasoning, raw evidence text, or provider internals, and MUST be false or absent when the final answer is fully grounded or a normal fallback.

#### Scenario: Disclaimed guidance sets diagnostic flag
- **WHEN** the assistant generates a `general_guidance_with_disclaimer` answer
- **THEN** response diagnostics include `llm_general_guidance_used: true`
- **AND** diagnostic `covered_aspects` and `missing_aspects` remain canonical requested aspect identifiers after answerability normalization

#### Scenario: Grounded answer does not set guidance flag
- **WHEN** the assistant returns a fully grounded answer from validated evidence
- **THEN** response diagnostics do not indicate that runtime-only general guidance was used

#### Scenario: Diagnostic metadata remains bounded
- **WHEN** diagnostics include `llm_general_guidance_used`
- **THEN** diagnostics exclude the disclaimed-guidance prompt, raw model reasoning, full retrieved evidence text, and unredacted provider internals
