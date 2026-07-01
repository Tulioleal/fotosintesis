## ADDED Requirements

### Requirement: Assistant frontend redesign preserves chat behavior
The assistant frontend SHALL preserve existing chat behavior while adopting the Fotosíntesis assistant layout and visual treatment.

#### Scenario: Chat request still uses assistant API
- **WHEN** a user sends a message from the redesigned `/assistant` page
- **THEN** the frontend sends the request through the existing `/api/assistant/chat` client behavior
- **AND** the redesign does not require backend API contract changes

#### Scenario: Conversation ID is preserved
- **WHEN** `/api/assistant/chat` returns or updates a conversation ID
- **THEN** subsequent assistant messages from the redesigned chat continue to include that conversation ID

#### Scenario: Plant taxonomy payload mapping is preserved
- **WHEN** the assistant page is opened with `plant`, `binomial`, and `scientific` query parameters
- **THEN** the redesigned frontend sends `plant`, `plant_binomial_name`, and `plant_scientific_name` in the assistant chat request using the existing mapping

#### Scenario: Plant-only requests remain compatible
- **WHEN** the assistant page is opened with only a `plant` query parameter
- **THEN** the redesigned frontend continues to send a compatible plant-only assistant request without requiring binomial or scientific-name fields

#### Scenario: Retryable failure remains recoverable
- **WHEN** the redesigned frontend receives a retryable machine-readable assistant failure from `/api/assistant/chat`
- **THEN** it shows the retryable error in a Fotosíntesis error or notice treatment
- **AND** it does not append an assistant message bubble for the failed generation
- **AND** it preserves any returned conversation ID for a later retry

#### Scenario: Assistant message content remains raw text
- **WHEN** an assistant response includes plain text, markdown-labeled content, or an unsupported future content format
- **THEN** the redesigned frontend renders the message content as raw text with whitespace preserved
- **AND** it does not parse markdown, render markdown syntax as HTML, or transform assistant prose into lists, links, headings, or emphasis

#### Scenario: Sources remain visible as source links
- **WHEN** an assistant response includes one or more structured sources
- **THEN** the redesigned frontend renders those sources as accessible links using the existing source title, domain, or URL fallback behavior
- **AND** the visual treatment follows the Fotosíntesis source-card or supporting-card style

#### Scenario: Pending state remains clear
- **WHEN** a user message is waiting for an assistant response
- **THEN** the redesigned frontend shows a clear pending state in the chat experience
- **AND** duplicate sends are prevented while the request is pending

### Requirement: Assistant entry links preserve query context
Assistant entry links from existing plant journeys SHALL remain valid and keep their query context after the assistant redesign.

#### Scenario: Identification assistant link keeps taxonomy context
- **WHEN** a confirmed identification candidate links to the assistant with plant, binomial, and scientific query parameters
- **THEN** the redesigned assistant route accepts those parameters without route changes
- **AND** the chat payload mapping remains available for the first and subsequent messages

#### Scenario: Adjacent plant screens are not redesigned
- **WHEN** this change is implemented
- **THEN** reminders, light-meter, garden detail, and plant profile screens are not visually redesigned beyond any minimal link or query-context preservation needed for assistant entry
