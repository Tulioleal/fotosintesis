## MODIFIED Requirements

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted-first web search for botanical questions when retrieved RAG evidence is insufficient and a specific plant context is available. The assistant SHALL use allowed-domain search results exclusively when any are returned, and SHALL select at most one external fallback result only when no allowed-domain search results are returned. The assistant SHALL construct trusted web fallback queries from the operational scientific name, a capped copy of the original user question, and trusted botanical source terms so unsupported botanical question intent is preserved.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning clarification or limitation text

#### Scenario: Unsupported botanical question terms are preserved in web query

- **WHEN** RAG and structured plant-data evidence are insufficient for a botanical question whose intent is not represented by the classified topic
- **THEN** the trusted web search query includes the operational scientific name and the relevant terms from the original user question
- **AND** the trusted web search query uses capped question context rather than only the generic classified topic

#### Scenario: Allowed-domain web results take precedence

- **WHEN** trusted web search returns one or more results whose source domains are in the allowed trusted-domain set
- **THEN** the assistant uses only those allowed-domain results for fallback answer evidence
- **AND** the assistant ignores external results from the same search response

#### Scenario: Single external fallback result allowed

- **WHEN** trusted web search returns zero results whose source domains are in the allowed trusted-domain set
- **AND** trusted web search returns one or more external results
- **THEN** the assistant selects at most one external result as fallback answer evidence

#### Scenario: Web fallback answer uses live evidence

- **WHEN** trusted-first web search returns usable allowed-domain or external fallback results after insufficient RAG evidence
- **THEN** the assistant answers from the selected web result snippets or fetched page content, identifies the evidence as live web evidence, and avoids presenting it as reviewed persisted knowledge

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources for the selected web result URLs, titles, domains and confidence context

#### Scenario: Trusted page fetch failure does not trigger external fallback

- **WHEN** trusted web search returns one or more allowed-domain results
- **AND** page fetching fails or extraction yields no usable page content for those results
- **THEN** the assistant does not select external fallback results for that search attempt
- **AND** existing snippet degradation or limitation behavior applies

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted-first web search fails or returns no usable selected results after insufficient RAG evidence
- **THEN** the assistant returns the existing degraded limitation or manual-search guidance instead of inventing unsupported botanical facts

### Requirement: Web fallback failures are tracked without blocking answers

The assistant MUST record trusted web-search or fallback persistence failures in tool failure metadata while still returning an answer when usable web evidence is available. The assistant MUST preserve fallback route metadata for attempted trusted web search even when the search tool fails before returning usable evidence.

#### Scenario: Search fails before fallback answer

- **WHEN** trusted web search fails and no sufficient RAG evidence exists
- **THEN** the assistant records the search failure and returns limitation or manual-search guidance
- **AND** the assistant response metadata includes the `web_search_used` fallback reason

#### Scenario: Persistence fails after fallback answer evidence exists

- **WHEN** trusted web search returns usable evidence but fallback evidence persistence fails
- **THEN** the assistant records the persistence failure and still returns the web-evidence answer with sources
