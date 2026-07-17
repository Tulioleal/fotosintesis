from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]


class TestIngestionKeyLanguageIndependence:
    def test_key_is_independent_of_keyword_matches(self):
        from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

        en_claim = {
            "scientific_name": "Rosa canina",
            "topic": "pruning",
            "source_url": "https://example.org/rose",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["season", "technique"],
            "claim": "Prune in late winter",
            "evidence_quote": "Best time to prune roses is late winter",
        }
        es_claim = {
            "scientific_name": "Rosa canina",
            "topic": "poda",
            "source_url": "https://example.org/rosal",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["temporada", "técnica"],
            "claim": "Podar a finales del invierno",
            "evidence_quote": "La mejor época para podar rosales es finales del invierno",
        }

        en_key = compute_claim_ingestion_key(en_claim)
        es_key = compute_claim_ingestion_key(es_claim)

        assert en_key != es_key, "Different languages must produce different keys"

    def test_synonymous_botanical_wording(self):
        from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

        claim1 = {
            "scientific_name": "Solanum lycopersicum",
            "topic": "watering",
            "source_url": "https://example.org/tomato-care",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["frequency"],
            "claim": "Water deeply once a week",
            "evidence_quote": "Deep watering weekly promotes root growth",
        }
        claim2 = {
            "scientific_name": "solanum lycopersicum",
            "topic": "Watering",
            "source_url": "https://example.org/tomato-care/",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["frequency"],
            "claim": "Water deeply once a week",
            "evidence_quote": "Deep watering weekly promotes root growth",
        }

        key1 = compute_claim_ingestion_key(claim1)
        key2 = compute_claim_ingestion_key(claim2)

        assert key1 == key2, "Case and trailing-slash normalization must produce identical keys"

    def test_paraphrased_evidence_generates_different_key(self):
        from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

        base = {
            "scientific_name": "Ficus elastica",
            "topic": "light",
            "source_url": "https://example.org/rubber-plant",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["brightness"],
            "claim": "Needs bright indirect light",
            "evidence_quote": "Bright indirect light is best for rubber plants",
        }
        paraphrased = {
            "scientific_name": "Ficus elastica",
            "topic": "light",
            "source_url": "https://example.org/rubber-plant",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["brightness"],
            "claim": "Needs bright indirect light",
            "evidence_quote": "Rubber trees thrive in bright filtered light",
        }

        base_key = compute_claim_ingestion_key(base)
        para_key = compute_claim_ingestion_key(paraphrased)

        assert base_key != para_key, "Different evidence must produce different keys"

    def test_no_keyword_based_routing(self):
        from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

        claim = {
            "scientific_name": "Orchidaceae",
            "topic": "general",
            "source_url": "https://example.org/orchid",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["care"],
            "claim": "Orchids need special care",
            "evidence_quote": "Orchids require well-draining medium",
        }
        key = compute_claim_ingestion_key(claim)
        assert key.startswith("v1:")
        assert len(key) > 10

    def test_spanish_supported_claim(self):
        from app.jobs.handlers.ingest_validated_claims import compute_claim_ingestion_key

        claim = {
            "scientific_name": "Lavandula angustifolia",
            "topic": "riego",
            "source_url": "https://example.org/lavanda",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "covered_aspects": ["frecuencia"],
            "claim": "Regar solo cuando el suelo esté seco",
            "evidence_quote": "La lavanda necesita poco riego",
        }
        key = compute_claim_ingestion_key(claim)
        assert key.startswith("v1:")

    def test_unsupported_multilingual_claims(self):
        from app.jobs.schemas import IngestValidatedClaimsPayload

        payload = IngestValidatedClaimsPayload(
            claims=[
                {
                    "scientific_name": "Test",
                    "topic": "test",
                    "source_url": "https://example.org/test",
                    "source_domain": "example.org",
                    "source_provenance": "trusted",
                    "claim": "Test claim",
                    "evidence_quote": "Test evidence",
                    "confidence": 0.0,
                    "covered_aspects": ["test"],
                    "answerability_status": "full",
                    "language": "fr",
                },
            ],
            conversation_id=uuid4(),
            answerability_status="full",
        )
        assert len(payload.claims) == 1
        assert payload.claims[0].language == "fr"


@pytest.mark.parametrize(
    ("status", "source_support"),
    [
        ("full", []),
        ("insufficient", [{"claim": "x", "source_urls": ["https://example.org"]}]),
        ("contradictory", [{"claim": "x", "source_urls": ["https://example.org"]}]),
        ("unsupported", [{"claim": "x", "source_urls": ["https://example.org"]}]),
    ],
)
def test_non_final_or_empty_semantic_states_build_no_claims(status, source_support):
    from app.assistant.graph.web_evidence import _validated_claim_payloads

    state = {
        "answerability_status": status,
        "source_support": source_support,
        "sources": [
            {
                "url": "https://example.org",
                "domain": "example.org",
                "source_provenance": "trusted",
            }
        ],
    }

    assert _validated_claim_payloads(
        state,
        scientific_name="Cotyledon tomentosa",
        topic="care",
    ) == []
