from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import types
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import (
    garden_plants,
    identification_candidates,
    identification_images,
    plant_profiles,
    recovery_tokens,
    sessions,
    users,
)
from app.core.settings import get_settings
from app.identification.gbif import GbifTaxonomy
from app.main import app
from app.providers.types import ConfidenceLabel, ImageAnalysisResult, PlantCandidate


@pytest.fixture(autouse=True)
def use_mock_providers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("JUDGE_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_registration_validation_and_duplicate_email(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post(
            "/auth/register", json={"name": "", "email": "bad", "password": "short"}
        )
        assert invalid.status_code == 422

        payload = {"name": "Tuli", "email": "tuli@example.com", "password": "password123"}
        created = await client.post("/auth/register", json=payload)
        assert created.status_code == 201
        assert created.json()["user"]["email_verified"] is False

        duplicate = await client.post("/auth/register", json=payload)
        assert duplicate.status_code == 409

    async with session_factory() as session:
        row = (
            await session.execute(select(users).where(users.c.email == "tuli@example.com"))
        ).first()
        assert row is not None
        assert row.email_verified is False
        assert row.password_hash.startswith("$argon2id$")


@pytest.mark.asyncio
async def test_registered_user_can_be_verified_from_fresh_repository_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        created = await repository.create_user("Ada", "ADA@example.com", "password123")

    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        verified = await repository.verify_credentials("ada@example.com", "password123")

    assert verified.id == created.id
    assert verified.email == "ada@example.com"


@pytest.mark.asyncio
async def test_password_recovery_returns_neutral_confirmation() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/auth/recovery/request", json={"email": "missing@example.com"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "If an account with that email exists" in response.json()["message"]


@pytest.mark.asyncio
async def test_password_recovery_persists_token_for_existing_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/auth/register",
            json={"name": "Lin", "email": "lin@example.com", "password": "password123"},
        )
        existing = await client.post(
            "/auth/recovery/request", json={"email": "lin@example.com"}
        )
        missing = await client.post(
            "/auth/recovery/request", json={"email": "missing@example.com"}
        )

    assert existing.status_code == 200
    assert missing.status_code == 200
    assert existing.json() == missing.json()

    async with session_factory() as session:
        rows = (await session.execute(select(recovery_tokens))).all()
        assert len(rows) == 2
        assert sum(row.user_id is not None for row in rows) == 1
        assert all(row.expires_at is not None for row in rows)


@pytest.mark.asyncio
async def test_protected_home_summary_requires_and_accepts_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthorized = await client.get("/home/summary")
        assert unauthorized.status_code == 401

        payload = {"name": "Ada", "email": "ada@example.com", "password": "password123"}
        await client.post("/auth/register", json=payload)
        verified = await client.post(
            "/auth/credentials/verify",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert verified.status_code == 200
        token = verified.json()["session_token"]

        async with session_factory() as session:
            row = (
                await session.execute(select(sessions).where(sessions.c.session_token == token))
            ).first()
            assert row is not None
            initial_expiration = row.expires

        summary = await client.get("/home/summary", headers={"Authorization": f"Bearer {token}"})
        assert summary.status_code == 200
        assert summary.json()["empty_state"] is True

        session_validation = await client.get(
            "/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        assert session_validation.status_code == 200
        assert session_validation.json() == {"status": "ok"}

        async with session_factory() as session:
            refreshed = (
                await session.execute(select(sessions).where(sessions.c.session_token == token))
            ).first()
            assert refreshed.expires >= initial_expiration

        logged_out = await client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert logged_out.status_code == 200

        invalidated = await client.get(
            "/home/summary", headers={"Authorization": f"Bearer {token}"}
        )
        assert invalidated.status_code == 401

        invalidated_session = await client.get(
            "/auth/session", headers={"Authorization": f"Bearer {token}"}
        )
        assert invalidated_session.status_code == 401

        async with session_factory() as session:
            row = (
                await session.execute(select(sessions).where(sessions.c.session_token == token))
            ).first()
            assert row.invalidated_at is not None


@pytest.mark.asyncio
async def test_home_summary_returns_garden_count_and_recent_garden_plants(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Sam", "sam@example.com", "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        token = auth_session.token

        monstera_id = uuid4()
        ficus_id = uuid4()
        sansevieria_id = uuid4()
        other_user_id = (
            await repository.create_user("Otto", "otto@example.com", "password123")
        ).id
        await session.execute(
            insert(plant_profiles).values(
                [
                    {
                        "id": monstera_id,
                        "scientific_name": "Monstera deliciosa",
                        "common_name": "Monstera Deliciosa",
                        "aliases": [],
                        "sections": {},
                        "sources": [],
                        "confidence": 0.92,
                        "limitations": [],
                    },
                    {
                        "id": ficus_id,
                        "scientific_name": "Ficus lyrata",
                        "common_name": "Ficus Lyrata",
                        "aliases": [],
                        "sections": {},
                        "sources": [],
                        "confidence": 0.88,
                        "limitations": [],
                    },
                    {
                        "id": sansevieria_id,
                        "scientific_name": "Sansevieria trifasciata",
                        "common_name": "Sansevieria",
                        "aliases": [],
                        "sections": {},
                        "sources": [],
                        "confidence": 0.81,
                        "limitations": [],
                    },
                ]
            )
        )

        newest_id = uuid4()
        middle_id = uuid4()
        oldest_id = uuid4()
        stranger_id = uuid4()
        await session.execute(
            insert(garden_plants).values(
                [
                    {
                        "id": oldest_id,
                        "user_id": user.id,
                        "profile_id": monstera_id,
                        "nickname": "Lobby monstera",
                        "location": "Living",
                        "image_path": "garden-plants/monstera.jpg",
                        "custom_data": {},
                        "active_reminders": 2,
                        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    },
                    {
                        "id": middle_id,
                        "user_id": user.id,
                        "profile_id": ficus_id,
                        "nickname": "Ficus de la sala",
                        "location": "Sala",
                        "image_path": "garden-plants/ficus.jpg",
                        "custom_data": {},
                        "active_reminders": 0,
                        "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
                    },
                    {
                        "id": newest_id,
                        "user_id": user.id,
                        "profile_id": sansevieria_id,
                        "nickname": None,
                        "location": "Dormitorio",
                        "image_path": None,
                        "custom_data": {},
                        "active_reminders": 1,
                        "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
                    },
                    {
                        "id": stranger_id,
                        "user_id": other_user_id,
                        "profile_id": monstera_id,
                        "nickname": None,
                        "location": None,
                        "image_path": None,
                        "custom_data": {},
                        "active_reminders": 0,
                        "created_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
                    },
                ]
            )
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/home/summary", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["garden_count"] == 3
    assert payload["empty_state"] is False

    recent = payload["recent_garden_plants"]
    assert [plant["id"] for plant in recent] == [str(newest_id), str(middle_id), str(oldest_id)]
    assert recent[0]["scientific_name"] == "Sansevieria trifasciata"
    assert recent[0]["common_name"] == "Sansevieria"
    assert recent[0]["nickname"] is None
    assert recent[0]["image_path"] is None
    assert recent[0]["location"] == "Dormitorio"
    assert recent[0]["active_reminders"] == 1
    assert recent[0]["created_at"].startswith("2026-06-01")

    assert recent[1]["scientific_name"] == "Ficus lyrata"
    assert recent[1]["common_name"] == "Ficus Lyrata"
    assert recent[1]["nickname"] == "Ficus de la sala"
    assert recent[1]["image_path"] == "garden-plants/ficus.jpg"
    assert recent[1]["location"] == "Sala"
    assert recent[1]["active_reminders"] == 0

    assert recent[2]["scientific_name"] == "Monstera deliciosa"
    assert recent[2]["nickname"] == "Lobby monstera"
    assert recent[2]["image_path"] == "garden-plants/monstera.jpg"
    assert recent[2]["location"] == "Living"
    assert recent[2]["active_reminders"] == 2


@pytest.mark.asyncio
async def test_home_summary_caps_recent_garden_plants_at_eight(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Nia", "nia@example.com", "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        token = auth_session.token

        profile_ids = [
            uuid4() for _ in range(10)
        ]
        await session.execute(
            insert(plant_profiles).values(
                [
                    {
                        "id": pid,
                        "scientific_name": f"Species {i}",
                        "common_name": f"Common {i}",
                        "aliases": [],
                        "sections": {},
                        "sources": [],
                        "confidence": 0.5,
                        "limitations": [],
                    }
                    for i, pid in enumerate(profile_ids)
                ]
            )
        )
        await session.execute(
            insert(garden_plants).values(
                [
                    {
                        "id": uuid4(),
                        "user_id": user.id,
                        "profile_id": profile_ids[i],
                        "nickname": None,
                        "location": None,
                        "image_path": None,
                        "custom_data": {},
                        "active_reminders": 0,
                        "created_at": datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                    }
                    for i in range(10)
                ]
            )
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/home/summary", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["garden_count"] == 10
    assert len(payload["recent_garden_plants"]) == 8
    assert [plant["scientific_name"] for plant in payload["recent_garden_plants"]] == [
        f"Species {i}" for i in range(9, 1, -1)
    ]


@pytest.mark.asyncio
async def test_home_summary_marks_empty_state_when_user_has_no_garden_plants(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Emi", "emi@example.com", "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/home/summary",
            headers={"Authorization": f"Bearer {auth_session.token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["garden_count"] == 0
    assert payload["empty_state"] is True
    assert payload["recent_garden_plants"] == []


@pytest.mark.asyncio
async def test_expired_persisted_session_is_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Grace", "grace@example.com", "password123")
        session_record = await repository.create_session(
            user.id,
            idle_ttl=timedelta(seconds=-1),
            absolute_ttl=timedelta(days=1),
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/home/summary", headers={"Authorization": f"Bearer {session_record.token}"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_identification_upload_validates_taxonomy_and_requires_confirmation(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "true")
    get_settings.cache_clear()

    async def matched_name(self, scientific_name: str) -> GbifTaxonomy:
        return GbifTaxonomy(
            key=123,
            accepted_key=456,
            accepted_scientific_name=scientific_name,
            binomial_name="Cotyledon tomentosa",
            taxonomic_status="ACCEPTED",
            synonyms=["Cotyledon ladismithiensis"],
            genus="Cotyledon",
            family="Crassulaceae",
            species=scientific_name,
            matched=True,
        )

    monkeypatch.setattr("app.identification.gbif.GbifClient.match_name", matched_name)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"name": "Mae", "email": "mae@example.com", "password": "password123"}
        await client.post("/auth/register", json=payload)
        verified = await client.post(
            "/auth/credentials/verify",
            json={"email": payload["email"], "password": payload["password"]},
        )
        token = verified.json()["session_token"]

        created = await client.post(
            "/identifications",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("plant.jpg", b"fake-image-bytes", "image/jpeg")},
        )

        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "needs_confirmation"
        assert body["candidates"][0]["validation_status"] == "validated"
        assert body["candidates"][0]["gbif_key"] == 123
        assert body["candidates"][0]["binomial_name"] == "Cotyledon tomentosa"
        assert body["candidates"][0]["accepted_scientific_name"] == "Cotyledon tomentosa"
        assert body["candidates"][0]["genus"] == "Cotyledon"
        assert body["candidates"][0]["family"] == "Crassulaceae"
        assert body["candidates"][0]["species"] == "Cotyledon tomentosa"

        confirmed = await client.post(
            f"/identifications/{body['id']}/candidates/{body['candidates'][0]['id']}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["candidate"]["confirmed_at"] is not None
        assert confirmed.json()["candidate"]["binomial_name"] == "Cotyledon tomentosa"

    async with session_factory() as session:
        image_rows = (await session.execute(select(identification_images))).all()
        candidate_rows = (await session.execute(select(identification_candidates))).all()
        assert len(image_rows) == 1
        assert len(candidate_rows) == 1
        assert candidate_rows[0].accepted_scientific_name == "Cotyledon tomentosa"
        assert candidate_rows[0].binomial_name == "Cotyledon tomentosa"


@pytest.mark.asyncio
async def test_identification_upload_with_openai_style_vision_does_not_return_maas_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeVisionProvider:
        async def analyze_image(
            self, image: bytes, prompt: str | None = None, **kwargs: object
        ) -> ImageAnalysisResult:
            assert kwargs["mime_type"] == "image/png"
            return ImageAnalysisResult(
                provider="openai-vision",
                model="gpt-4.1-mini",
                description="OpenAI-style mocked visual analysis found a plant.",
                candidates=[
                    PlantCandidate(
                        scientific_name="Pilea peperomioides",
                        common_name="Chinese money plant",
                        confidence_label=ConfidenceLabel.medium,
                        visible_traits=["round green leaves"],
                        provider="openai-vision",
                    )
                ],
                metadata={"image_size_bytes": len(image), "prompt": prompt},
            )

    async def matched_name(self, scientific_name: str) -> GbifTaxonomy:
        return GbifTaxonomy(
            key=321,
            accepted_key=654,
            accepted_scientific_name=scientific_name,
            taxonomic_status="ACCEPTED",
            genus="Pilea",
            family="Urticaceae",
            species=scientific_name,
            matched=True,
        )

    monkeypatch.setattr(
        "app.api.identifications.get_provider_registry",
        lambda: types.SimpleNamespace(vision=FakeVisionProvider()),
    )
    monkeypatch.setattr("app.identification.gbif.GbifClient.match_name", matched_name)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"name": "Opal", "email": "opal@example.com", "password": "password123"}
        await client.post("/auth/register", json=payload)
        verified = await client.post(
            "/auth/credentials/verify",
            json={"email": payload["email"], "password": payload["password"]},
        )
        token = verified.json()["session_token"]

        response = await client.post(
            "/identifications",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("plant.png", b"fake-png-bytes", "image/png")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["sad_path"] != "maas_unavailable"
    assert body["sad_path"] is None
    assert body["status"] == "needs_confirmation"
    assert body["candidates"][0]["suggested_scientific_name"] == "Pilea peperomioides"


@pytest.mark.asyncio
async def test_identification_reports_no_gbif_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def missing_name(self, scientific_name: str) -> GbifTaxonomy:
        return GbifTaxonomy()

    monkeypatch.setattr("app.identification.gbif.GbifClient.match_name", missing_name)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"name": "Noe", "email": "noe@example.com", "password": "password123"}
        await client.post("/auth/register", json=payload)
        verified = await client.post(
            "/auth/credentials/verify",
            json={"email": payload["email"], "password": payload["password"]},
        )
        token = verified.json()["session_token"]

        response = await client.post(
            "/identifications",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("plant.png", b"fake-image-bytes", "image/png")},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "retry_needed"
        assert body["sad_path"] == "no_gbif_match"
        assert body["candidates"][0]["binomial_name"] is None
