import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.providers.factory import get_provider_registry


@pytest.mark.asyncio
async def test_health_reports_mock_provider_dependencies() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"]["model_provider"] == "MockModelProvider"
    assert payload["dependencies"]["vision_provider"] == "MockVisionPlantIdentificationProvider"
    assert payload["dependencies"]["embedding_provider"] == "MockEmbeddingProvider"
    assert payload["dependencies"]["search_provider"] == "MockSearchProvider"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_text() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health")
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "fotosintesis_requests_total" in response.text


@pytest.mark.asyncio
async def test_mock_provider_registry_returns_deterministic_local_providers() -> None:
    providers = get_provider_registry()

    text = await providers.model.generate_text("care prompt")
    image = await providers.vision.analyze_image(b"fake-image")
    search = await providers.search.search("Cotyledon tomentosa care")
    embeddings = await providers.embeddings.create_embeddings(["bright light"])

    assert text.provider == "mock-model"
    assert image.candidates[0].scientific_name == "Cotyledon tomentosa"
    assert search[0].source_domain == "example.org"
    assert embeddings.provider == "mock-embedding"
    assert len(embeddings.embeddings[0]) > 0
