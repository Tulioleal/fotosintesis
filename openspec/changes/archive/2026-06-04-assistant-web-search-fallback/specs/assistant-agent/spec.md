## ADDED Requirements

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted web search for botanical questions when retrieved RAG evidence is insufficient and a specific plant context is available.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning clarification or limitation text

#### Scenario: Web fallback answer uses live evidence

- **WHEN** trusted web search returns usable results after insufficient RAG evidence
- **THEN** the assistant answers from the web result snippets, identifies the evidence as live web evidence, and avoids presenting it as reviewed persisted knowledge

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources for the web result URLs, titles, domains and confidence context

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted web search fails or returns no usable results after insufficient RAG evidence
- **THEN** the assistant returns the existing degraded limitation or manual-search guidance instead of inventing unsupported botanical facts

### Requirement: Web fallback failures are tracked without blocking answers

The assistant MUST record trusted web-search or fallback persistence failures in tool failure metadata while still returning an answer when usable web evidence is available.

#### Scenario: Search fails before fallback answer

- **WHEN** trusted web search fails and no sufficient RAG evidence exists
- **THEN** the assistant records the search failure and returns limitation or manual-search guidance

#### Scenario: Persistence fails after fallback answer evidence exists

- **WHEN** trusted web search returns usable evidence but fallback evidence persistence fails
- **THEN** the assistant records the persistence failure and still returns the web-evidence answer with sources
