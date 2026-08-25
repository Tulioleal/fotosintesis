## MODIFIED Requirements
### Requirement: Multilingual care intent classification

The assistant plant-care answer pipeline SHALL classify user input before retrieval using a closed multilingual classifier contract that includes `language`, `answer_language`, `intent`, `topic`, `required_aspects`, `plant_reference`, `confidence`, `needs_retrieval` — and, for reminder intents, the schema-declared reminder scheduling fields `reminder_action`, `reminder_recurrence`, `reminder_due_at`, and `reminder_suggestion_requested`. Reminder-driven routing and creation SHALL activate only from schema-valid classifier output carrying those fields or from explicit structured request context; reading reminder fields from undeclared raw classifier output SHALL NOT occur. Classifier output MUST pass schema validation before it can drive routing, retrieval, or reminder actions. Deterministic Spanish-keyword-based semantic intent detection SHALL NOT be used; the multilingual LLM classifier and explicit request fields are the sole semantic-intent path. Non-semantic safety boundaries MAY remain deterministic.

#### Scenario: Reminder fields arrive only through the declared schema

- WHEN the chat reminder branch evaluates classifier output for action, recurrence, due date, or suggestion-request signals
- THEN it reads only schema-validated reminder scheduling fields from the classified result
- AND undeclared or raw-output reminder fields are treated as absent

#### Scenario: Reminder intent without complete schedule fields

- WHEN schema-valid classifier output indicates a reminder request with missing action, date, time, or recurrence values
- THEN the assistant asks for the missing information before any creation