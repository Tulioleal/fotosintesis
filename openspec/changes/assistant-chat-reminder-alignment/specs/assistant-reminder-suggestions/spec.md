## MODIFIED Requirements
### Requirement: Evidence-grounded reminder suggestion contract

Chat-origin reminder suggestions SHALL carry the same grounding payload as page-flow suggestions: the evidence context used to derive them, a confidence indication, limitations, and a concise justification, together with the effective IANA timezone and explicit local date and time. Suggestions flagged as requiring confirmation SHALL be presented for review before creation and MUST NOT auto-create. The justification SHALL persist with the created reminder.

#### Scenario: Chat suggestion reaches payload parity

- WHEN an assistant conversation produces a reminder suggestion
- THEN the suggestion schema matches the page-flow suggestion contract for evidence, confidence, limitations, justification, timezone, and explicit local schedule fields

#### Scenario: Confirmation flag is honored

- WHEN a chat-origin suggestion is flagged as requiring confirmation
- THEN the frontend presents the confirmation card and creates only after explicit acceptance
- AND duplicate acceptance is disabled while creation is in progress

### Requirement: Timezone-aware reminder suggestions

Assistant-origin reminder suggestions SHALL carry an effective IANA timezone and explicit local date and time fields through display and acceptance so the created reminder schedules at the intended local time. The frontend SHALL NOT derive local schedule values by slicing formatted timestamps.

#### Scenario: Suggestion carries effective timezone

- WHEN an assistant chat response includes a reminder suggestion requiring confirmation
- THEN the suggestion includes the effective IANA timezone used to interpret its due date and time

#### Scenario: Accepted suggestion schedules in effective timezone

- WHEN the user accepts an assistant-origin reminder suggestion
- THEN the system creates the reminder through the reminders API using the suggestion's effective timezone and local date and time
- AND the acceptance payload does not reconstruct date or time by string-splitting an instant