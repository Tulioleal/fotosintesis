from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import identification_candidates, identification_images
from app.main import app
from app.storage.local import LocalObjectStorage
from app.storage.models import ObjectUpload

IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
IMAGE_PATH = "identifications/owner/plant.jpg"


async def _create_owner(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    storage_path: str,
) -> tuple[str, str]:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Ada", email, "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )

        image_id = uuid4()
        candidate_id = uuid4()
        await session.execute(
            insert(identification_images).values(
                id=image_id,
                user_id=user.id,
                storage_path=storage_path,
                mime_type="image/jpeg",
                size_bytes=len(IMAGE_BYTES),
                metadata={},
                status="needs_confirmation",
            )
        )
        await session.execute(
            insert(identification_candidates).values(
                id=candidate_id,
                identification_id=image_id,
                common_name="Helecho",
                suggested_scientific_name="Nephrolepis exaltata",
                confidence_label="high",
                visible_traits=[],
                possible_match_copy="Matches a domestic fern.",
                accepted_scientific_name="Nephrolepis exaltata",
                binomial_name="Nephrolepis exaltata",
                validation_status="validated",
                confirmed_at=datetime.now(timezone.utc),
                user_id=user.id,
            )
        )
        await session.commit()
        return auth_session.token, str(candidate_id)


@pytest.fixture
def storage(tmp_path):
    return LocalObjectStorage(bucket="test-bucket", root=tmp_path / "storage")


@pytest.mark.asyncio
async def test_owner_saves_and_fetches_identification_image_with_private_headers(
    session_factory: async_sessionmaker[AsyncSession],
    storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, candidate_id = await _create_owner(
        session_factory, email="owner@example.com", storage_path=IMAGE_PATH
    )
    await storage.put_object(_upload(IMAGE_PATH))
    monkeypatch.setattr("app.api.profile_garden.get_object_storage", lambda: storage)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.post(
            "/garden",
            json={"confirmed_candidate_id": candidate_id, "image_path": IMAGE_PATH},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert saved.status_code == 201, saved.text
        plant_id = saved.json()["id"]
        assert saved.json()["image_path"] == IMAGE_PATH

        fetched = await client.get(
            f"/garden/{plant_id}/image",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert fetched.status_code == 200
    assert fetched.content == IMAGE_BYTES
    assert fetched.headers["content-type"].startswith("image/jpeg")
    assert fetched.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_owner_can_save_image_candidate_without_candidate_user_id(
    session_factory: async_sessionmaker[AsyncSession],
    storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, candidate_id = await _create_owner(
        session_factory, email="legacy-owner@example.com", storage_path=IMAGE_PATH
    )
    async with session_factory() as session:
        await session.execute(
            update(identification_candidates)
            .where(identification_candidates.c.id == candidate_id)
            .values(user_id=None)
        )
        await session.commit()

    await storage.put_object(_upload(IMAGE_PATH))
    monkeypatch.setattr("app.api.profile_garden.get_object_storage", lambda: storage)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.post(
            "/garden",
            json={"confirmed_candidate_id": candidate_id, "image_path": IMAGE_PATH},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert saved.status_code == 201, saved.text
    assert saved.json()["image_path"] == IMAGE_PATH


@pytest.mark.asyncio
async def test_other_user_cannot_fetch_someone_elses_plant_image(
    session_factory: async_sessionmaker[AsyncSession],
    storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_token, owner_candidate = await _create_owner(
        session_factory, email="owner2@example.com", storage_path=IMAGE_PATH
    )
    intruder_token, _ = await _create_owner(
        session_factory, email="intruder@example.com", storage_path="identifications/x/y.jpg"
    )
    await storage.put_object(_upload(IMAGE_PATH))
    monkeypatch.setattr("app.api.profile_garden.get_object_storage", lambda: storage)

    # Separate clients so each user carries only their own session state.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as owner_client:
        saved = await owner_client.post(
            "/garden",
            json={"confirmed_candidate_id": owner_candidate, "image_path": IMAGE_PATH},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        plant_id = saved.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as intruder_client:
        intruder_response = await intruder_client.get(
            f"/garden/{plant_id}/image",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )

    anonymous_response = await AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ).get(f"/garden/{plant_id}/image")

    assert intruder_response.status_code == 404
    assert anonymous_response.status_code == 401


@pytest.mark.asyncio
async def test_save_rejects_image_paths_not_owned_by_the_caller(
    session_factory: async_sessionmaker[AsyncSession],
    storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, foreign_candidate = await _create_owner(
        session_factory, email="foreign@example.com", storage_path="identifications/foreign/f.jpg"
    )
    token, own_candidate = await _create_owner(
        session_factory, email="saver@example.com", storage_path=IMAGE_PATH
    )
    monkeypatch.setattr("app.api.profile_garden.get_object_storage", lambda: storage)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        foreign_reference = await client.post(
            "/garden",
            json={
                "confirmed_candidate_id": own_candidate,
                "image_path": "identifications/foreign/f.jpg",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        arbitrary_reference = await client.post(
            "/garden",
            json={
                "confirmed_candidate_id": own_candidate,
                "image_path": "../../etc/passwd.jpg",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        mismatched_candidate = await client.post(
            "/garden",
            json={
                "confirmed_candidate_id": foreign_candidate,
                "image_path": IMAGE_PATH,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert foreign_reference.status_code == 422
    assert arbitrary_reference.status_code == 422
    # The foreign candidate belongs to another user entirely, so the save is
    # rejected with the standard confirmed-candidate conflict instead.
    assert mismatched_candidate.status_code == 409


@pytest.mark.asyncio
async def test_missing_stored_object_returns_404(
    session_factory: async_sessionmaker[AsyncSession],
    storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, candidate_id = await _create_owner(
        session_factory, email="missing@example.com", storage_path=IMAGE_PATH
    )
    monkeypatch.setattr("app.api.profile_garden.get_object_storage", lambda: storage)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.post(
            "/garden",
            json={"confirmed_candidate_id": candidate_id, "image_path": IMAGE_PATH},
            headers={"Authorization": f"Bearer {token}"},
        )
        plant_id = saved.json()["id"]
        fetched = await client.get(
            f"/garden/{plant_id}/image",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert fetched.status_code == 404


def _upload(path: str):
    return ObjectUpload(path=path, content=IMAGE_BYTES, mime_type="image/jpeg")
