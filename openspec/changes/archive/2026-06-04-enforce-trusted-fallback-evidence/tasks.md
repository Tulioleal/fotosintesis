## 1. Trusted Validation Wiring

- [x] 1.1 Instantiate or inject `TrustedSourceValidator` in assistant fallback tooling without changing existing acquisition validation semantics
- [x] 1.2 Pass configured trusted source domains as `allowed_domains` when `trusted_web_search(...)` calls the search provider
- [x] 1.3 Filter `ingest_web_evidence(...)` inputs through `TrustedSourceValidator` before building `KnowledgeDocumentInput`
- [x] 1.4 Return a non-blocking ingestion failure or limitation when no fallback results pass trusted-source validation

## 2. Persistence Behavior

- [x] 2.1 Ensure mixed fallback results persist only trusted sources, snippets and metadata
- [x] 2.2 Ensure untrusted fallback results are not chunked, embedded, indexed or stored as knowledge sources
- [x] 2.3 Preserve assistant fallback answer generation and response behavior when persistence is skipped or fails

## 3. Test Coverage

- [x] 3.1 Add or update assistant tool tests proving untrusted fallback results are not persisted
- [x] 3.2 Add or update tests proving mixed fallback results ingest only trusted evidence
- [x] 3.3 Add or update fallback search tests proving `allowed_domains` is passed to providers that accept it
- [x] 3.4 Run the relevant backend test suite for assistant fallback and knowledge acquisition behavior
