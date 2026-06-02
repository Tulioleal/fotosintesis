import pytest

from app.knowledge.plant_data import PlantDataLookupService
from app.providers.mocks import MockPerenualPlantDataProvider, MockTreflePlantDataProvider


@pytest.mark.asyncio
async def test_trefle_sufficient_evidence_skips_perenual() -> None:
    trefle = MockTreflePlantDataProvider(mode="care")
    perenual = MockPerenualPlantDataProvider()

    evidence = await PlantDataLookupService(trefle=trefle, perenual=perenual).lookup(
        scientific_name="Cotyledon tomentosa", topic="watering"
    )

    assert evidence is not None
    assert evidence.sufficient is True
    assert evidence.providers == ["mock-trefle"]
    assert trefle.calls == ["Cotyledon tomentosa"]
    assert perenual.calls == []


@pytest.mark.asyncio
async def test_perenual_complements_missing_care_fields() -> None:
    trefle = MockTreflePlantDataProvider(mode="botanical")
    perenual = MockPerenualPlantDataProvider()

    evidence = await PlantDataLookupService(trefle=trefle, perenual=perenual).lookup(
        scientific_name="Cotyledon tomentosa", topic="watering"
    )

    assert evidence is not None
    assert evidence.sufficient is True
    assert evidence.providers == ["mock-trefle", "mock-perenual"]
    assert "watering" in evidence.fields
    assert perenual.calls == ["Cotyledon tomentosa"]


@pytest.mark.asyncio
async def test_lookup_rejects_non_scientific_name_without_provider_calls() -> None:
    trefle = MockTreflePlantDataProvider(mode="care")
    perenual = MockPerenualPlantDataProvider()

    evidence = await PlantDataLookupService(trefle=trefle, perenual=perenual).lookup(
        scientific_name="bear", topic="watering"
    )

    assert evidence is None
    assert trefle.calls == []
    assert perenual.calls == []


@pytest.mark.asyncio
async def test_structured_evidence_uses_auto_ingested_document() -> None:
    trefle = MockTreflePlantDataProvider(mode="care")
    perenual = MockPerenualPlantDataProvider()

    evidence = await PlantDataLookupService(trefle=trefle, perenual=perenual).lookup(
        scientific_name="Cotyledon tomentosa", topic="watering"
    )

    assert evidence is not None
    document = evidence.to_document()
    assert document.review_status.value == "auto_ingested"
    assert document.sources[0].validation_status == "structured_api"
    assert "mock-trefle" in document.content
