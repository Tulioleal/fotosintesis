"""Search API endpoint tests.

Covers local ranking, GBIF fallback, duplicate collapse, provider-error
retryability, manual candidate creation and confirmation reuse, and ownership.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import identification_candidates, plant_profiles
from app.core.settings import get_settings
from app.identification.gbif import GbifTaxonomy, ProviderLookupError
from app.main import app


def _enable_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "true")
    get_settings.cache_clear()


async def _authed_client(session_factory) -> tuple[AsyncClient, object]:
    async with session_factory() as session:
        auth = DatabaseAuthRepository(session)
        user = await auth.create_user("Owner", f"{uuid4()}@example.com", "password123")
        auth_session = await auth.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        token = auth_session.token
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    client.headers["Authorization"] = f"Bearer {token}"
    return client, user


async def _create_local_profile(
    session_factory, *, scientific_name: str, common_name: str | None = None,
    normalized_binomial: str | None = None,
) -> None:
    async with session_factory() as session:
        await session.execute(
            insert(plant_profiles).values(
                id=uuid4(),
                scientific_name=scientific_name,
                common_name=common_name,
                aliases=[{"name": "Hoja partida", "language": "es"}],
                sections={"care": ["Content."]},
                sources=[],
                confidence=0.5,
                limitations=[],
                normalized_binomial=normalized_binomial,
            )
        )
        await session.commit()


async def _create_manual_candidate(
    session_factory, *, user_id, query="Monstera deliciosa",
) -> str:
    from app.identification.repository import IdentificationRepository

    async with session_factory() as session:
        candidate = await IdentificationRepository(session).create_manual_candidate(
            user_id=user_id,
            query=query,
            taxonomy=GbifTaxonomy(
                key=2878688,
                accepted_key=2878688,
                accepted_scientific_name="Monstera deliciosa Liebm.",
                binomial_name="Monstera deliciosa",
                taxonomic_status="ACCEPTED",
                rank="SPECIES",
                genus="Monstera",
                family="Araceae",
                species="Monstera deliciosa",
                matched=True,
            ),
        )
        return str(candidate.id)


async def test_search_requires_authentication(session_factory) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/search?q=Monstera")
    assert response.status_code == 401


async def test_local_search_returns_matched_profile(session_factory) -> None:
    client, _ = await _authed_client(session_factory)
    try:
        await _create_local_profile(
            session_factory,
            scientific_name="Monstera deliciosa",
            common_name="Costilla de Adán",
            normalized_binomial="Monstera deliciosa",
        )
        response = await client.get("/search", params={"q": "Monstera"})
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 1
        result = body["results"][0]
        assert result["scientific_name"] == "Monstera deliciosa"
        assert result["matched_field"] == "scientific_name"
        assert result["has_evidence"] is True
    finally:
        await client.aclose()


async def test_gbif_search_returns_candidates_and_collapses_duplicates(
    session_factory, monkeypatch,
) -> None:
    client, _ = await _authed_client(session_factory)
    try:
        async def fake_suggest(query, limit=8):
            return [
                GbifTaxonomy(key=1, accepted_key=100, binomial_name="Monstera deliciosa", rank="SPECIES", matched=True),
                GbifTaxonomy(key=2, accepted_key=100, binomial_name="Monstera deliciosa", rank="SPECIES", matched=True),
                GbifTaxonomy(key=3, accepted_key=None, binomial_name="Monstera", rank="GENUS", matched=True),
            ]

        monkeypatch.setattr(
            "app.api.search.GbifClient.suggest", fake_suggest
        )
        response = await client.get("/search/gbif", params={"q": "Monstera"})
        assert response.status_code == 200
        body = response.json()
        # Duplicate accepted key 100 collapses to a single candidate.
        assert len(body["candidates"]) == 2
        keys = [c["accepted_key"] for c in body["candidates"]]
        assert 100 in keys
    finally:
        await client.aclose()


async def test_gbif_search_provider_error_is_retryable(session_factory, monkeypatch) -> None:
    client, _ = await _authed_client(session_factory)
    try:
        async def fake_suggest(query, limit=8):
            raise ProviderLookupError("down")

        monkeypatch.setattr(
            "app.api.search.GbifClient.suggest", fake_suggest
        )
        response = await client.get("/search/gbif", params={"q": "Monstera"})
        assert response.status_code == 503
    finally:
        await client.aclose()


async def test_create_manual_candidate_via_api(session_factory) -> None:
    client, user = await _authed_client(session_factory)
    try:
        response = await client.post(
            "/search/candidates",
            json={
                "query": "Monstera deliciosa",
                "gbif": {
                    "key": 2878688,
                    "accepted_key": 2878688,
                    "accepted_scientific_name": "Monstera deliciosa Liebm.",
                    "binomial_name": "Monstera deliciosa",
                    "rank": "SPECIES",
                    "taxonomic_status": "ACCEPTED",
                    "genus": "Monstera",
                    "family": "Araceae",
                    "species": "Monstera deliciosa",
                    "synonyms": [],
                },
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["validation_status"] == "validated"
        assert body["confidence_label"] == "manual"
    finally:
        await client.aclose()


async def test_create_manual_candidate_rejects_invalid_identity(session_factory) -> None:
    client, _ = await _authed_client(session_factory)
    try:
        response = await client.post(
            "/search/candidates",
            json={
                "query": "Monstera",
                "gbif": {
                    "key": 1,
                    "accepted_key": 1,
                    "binomial_name": None,
                },
            },
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


async def test_confirm_manual_candidate_reuses_enrichment(
    session_factory, monkeypatch,
) -> None:
    _enable_producer(monkeypatch)
    client, user = await _authed_client(session_factory)
    try:
        candidate_id = await _create_manual_candidate(session_factory, user_id=user.id)
        response = await client.post(f"/search/candidates/{candidate_id}/confirm")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "confirmed"
        assert body["enrichment"]["job"]["status"] == "pending"
    finally:
        await client.aclose()


async def test_confirm_manual_candidate_blocks_unowned(session_factory, monkeypatch) -> None:
    _enable_producer(monkeypatch)
    client, user = await _authed_client(session_factory)
    try:
        candidate_id = await _create_manual_candidate(session_factory, user_id=user.id)
        # A second user cannot confirm someone else's candidate.
        other_client, _ = await _authed_client(session_factory)
        try:
            response = await other_client.post(f"/search/candidates/{candidate_id}/confirm")
            assert response.status_code == 409
        finally:
            await other_client.aclose()
    finally:
        await client.aclose()


async def test_search_does_not_semantically_classify_non_matching_terms(
    session_factory,
) -> None:
    """Search is textual name matching, never keyword-based semantic
    classification: a non-English/synonym term that does not textually match a
    local name yields no local results and routes to the external path."""
    client, _ = await _authed_client(session_factory)
    try:
        await _create_local_profile(
            session_factory,
            scientific_name="Monstera deliciosa",
            common_name="Costilla de Adán",
            normalized_binomial="Monstera deliciosa",
        )

        # A common-name synonym not stored in any local field must not match
        # through keyword semantics.
        response = await client.get("/search", params={"q": "Hoja de queso"})
        assert response.status_code == 200
        assert response.json()["results"] == []

        # An unrelated term in another language likewise yields no local match.
        response = await client.get("/search", params={"q": "schweizerkäsepflanze"})
        assert response.status_code == 200
        assert response.json()["results"] == []

        # A real textual match still works.
        response = await client.get("/search", params={"q": "Costilla"})
        assert response.status_code == 200
        assert len(response.json()["results"]) == 1
    finally:
        await client.aclose()
