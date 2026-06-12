## MODIFIED Requirements

### Requirement: Trusted web fallback for insufficient botanical evidence

The assistant SHALL run trusted-first web search for botanical questions when retrieved RAG evidence is missing or not directly answerable and a specific plant context is available. The assistant SHALL also run trusted web search when structured plant-data evidence exists but is not directly answerable for the user's exact question. The assistant SHALL use allowed-domain search results exclusively when any are returned, and SHALL select at most one external fallback result only when no allowed-domain search results are returned. The assistant SHALL construct trusted web fallback queries from the operational scientific name, a capped copy of the original user question, and trusted botanical source terms so unsupported botanical question intent is preserved. The assistant MUST validate each selected fallback source independently against the requested missing care aspects before using that source for answer synthesis or response source attribution.

#### Scenario: Degraded RAG triggers web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns insufficient chunks or degraded limitations
- **THEN** the assistant calls trusted web search before returning clarification or limitation text

#### Scenario: Non-answerable RAG triggers structured then web fallback

- **WHEN** a botanical question has a selected plant or plant hint and RAG retrieval returns chunks that do not directly answer the question
- **THEN** the assistant attempts structured plant-data lookup before trusted web search
- **AND** calls trusted web search when structured plant-data evidence is missing or not directly answerable

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

- **WHEN** trusted-first web search returns usable allowed-domain or external fallback results after insufficient RAG evidence or non-answerable structured evidence
- **THEN** the assistant validates each usable fallback source independently against the requested missing aspects before answer generation
- **AND** answers only from independently validated source snippets or fetched page content
- **AND** identifies the evidence as live web evidence and avoids presenting it as reviewed persisted knowledge

#### Scenario: Web fallback sources are exposed

- **WHEN** the assistant answers from trusted web-search results
- **THEN** the assistant response metadata includes sources only for independently validated web result URLs, titles, domains and confidence context

#### Scenario: Trusted page fetch failure does not trigger external fallback

- **WHEN** trusted web search returns one or more allowed-domain results
- **AND** page fetching fails or extraction yields no usable page content for those results
- **THEN** the assistant does not select external fallback results for that search attempt
- **AND** existing snippet degradation or limitation behavior applies

#### Scenario: Web fallback unavailable preserves limitations

- **WHEN** trusted-first web search fails or returns no usable selected results after insufficient or non-answerable RAG and structured evidence
- **THEN** the assistant returns the existing degraded limitation or manual-search guidance instead of inventing unsupported botanical facts unless conservative safety fallback applies

#### Scenario: Off-aspect trusted source excluded from prompt and response sources

- **WHEN** trusted web fallback returns one source that independently validates for a requested watering aspect and another trusted source that covers no requested missing aspect
- **THEN** the assistant includes only the validated watering source in the answer synthesis prompt
- **AND** the assistant response source metadata includes only the validated watering source

#### Scenario: Partial web validation leaves missing aspects unresolved

- **WHEN** a web fallback source independently validates for only one of multiple requested missing non-critical aspects
- **THEN** the assistant treats that source as evidence only for the validated aspect
- **AND** the assistant keeps the remaining requested aspects missing for partial-answer or limitation handling

#### Scenario: Safety-sensitive web source must validate independently

- **WHEN** the requested missing aspect is pet toxicity, human edibility or another safety-sensitive aspect
- **THEN** each web source must independently satisfy direct-evidence checks and the safety validation threshold before the assistant uses that source
- **AND** the assistant returns conservative safety guidance when no source independently validates for the safety-sensitive aspect
