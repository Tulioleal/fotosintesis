## MODIFIED Requirements

### Requirement: Trusted source acquisition

The system MUST restrict incremental acquisition to approved or explicitly validated trusted sources, regardless of whether search results come from the mock search provider or the configured OpenAI search provider.

#### Scenario: Untrusted source is sole result

- **WHEN** only blogs, stores, unmoderated forums or non-persistent URLs are available
- **THEN** the system does not use them as the sole basis for persistent knowledge

#### Scenario: OpenAI search returns mixed trust results

- **WHEN** OpenAI-backed search returns both trusted and untrusted source URLs
- **THEN** the acquisition flow uses the existing trusted-source validation rules before persisting or using acquired knowledge
