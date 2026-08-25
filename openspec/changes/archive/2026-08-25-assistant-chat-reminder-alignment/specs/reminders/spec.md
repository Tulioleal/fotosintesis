## MODIFIED Requirements
### Requirement: Backend-generated reminder suggestions

AI-labeled reminder suggestions SHALL originate from a backend operation that accepts a selected garden plant and an optional user request, resolves the plant's confirmed taxonomy through existing ownership checks, and loads profile evidence, garden location, notes, active reminders, and timezone before proposing a suggestion. The frontend SHALL NOT generate AI-labeled suggestions with local semantic regular expressions or fixed calendar defaults, and SHALL NOT rewrite, normalize, or remap backend-supplied action values through local semantic mappings on any acceptance surface, including assistant chat.

#### Scenario: Chat acceptance preserves backend semantics

- WHEN the user accepts an assistant-origin reminder suggestion from chat
- THEN the creation request carries the backend-supplied action value unchanged
- AND no client-side regex or keyword mapping alters the action before creation