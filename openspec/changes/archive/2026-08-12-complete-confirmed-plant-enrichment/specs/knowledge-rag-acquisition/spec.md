## ADDED Requirements

### Requirement: Enrichment source-support binding without lexical authority

Offline enrichment evidence persistence SHALL bind normalized semantic source support to supplied canonical source packages without using exact quote substring, keyword, regex, translated-term, token-presence, or language-specific matching as evidence-coverage authority. Deterministic checks SHALL remain limited to schema validity, canonical requested aspects, source identity, trust status, non-empty claim and quote, and safety thresholds.

#### Scenario: Judge returns source-bound semantic paraphrase
- **WHEN** final combined judging accepts a requested aspect from a supplied trusted source and returns a non-empty paraphrased evidence quote
- **THEN** the support is not rejected solely because the quote is not an exact substring of normalized source text

#### Scenario: Judge returns structurally invalid support
- **WHEN** final combined judging omits canonical requested aspects, a supplied source identity, a non-empty claim, or a non-empty evidence quote
- **THEN** that support is excluded from persistence and indexing

### Requirement: Enrichment aspect metadata repair on reuse

Reused enrichment evidence SHALL expose the complete relationally accepted canonical aspect set to vector indexing after every successful aspect-association update. Vector metadata refresh SHALL use stable node identities and MUST NOT duplicate content, chunks, embeddings, or nodes.

#### Scenario: Reused content receives additional support
- **WHEN** an existing enrichment document receives an idempotent association for an additional canonical aspect
- **THEN** its vector retrieval metadata is refreshed from authoritative relational state
- **AND** later retrieval filtered by that aspect can find the existing document

#### Scenario: Vector refresh retries
- **WHEN** vector metadata refresh fails after relational support commits
- **THEN** retry converges the stable vector nodes from current relational metadata
- **AND** does not duplicate relational or vector effects
