## 1. Backend Assistant Payload

- [x] 1.1 Add a structured assistant reminder suggestion schema to the chat response model and generated API contract
- [x] 1.2 Update reminder-intent handling to return a suggestion payload when the assistant proposes a complete reminder that requires confirmation
- [x] 1.3 Preserve direct reminder creation when the user explicitly requests creation with plant, action, due date, due time and recurrence

## 2. Frontend Confirmation UI

- [x] 2.1 Extend frontend assistant API types to include the optional reminder suggestion payload
- [x] 2.2 Render assistant-origin reminder suggestion confirmation cards in the chat thread with plant, schedule, recurrence and justification details
- [x] 2.3 Wire the confirmation action to create the reminder through the existing reminders API with duplicate-submit protection and success/error feedback

## 3. Verification

- [x] 3.1 Add backend coverage for assistant responses that include structured reminder suggestions and for direct explicit reminder creation remaining unchanged
- [x] 3.2 Add frontend component coverage for displaying and accepting assistant reminder suggestions
- [x] 3.3 Run the relevant backend and frontend test suites for assistant/reminder behavior
