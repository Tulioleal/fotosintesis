from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import garden_plants, light_measurements, plant_profiles
from app.main import app


@pytest.mark.asyncio
async def test_create_light_measurement_with_optional_garden_plant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, garden_id = await _create_user_garden_plant(session_factory, email="light@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/light-measurements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "garden_plant_id": garden_id,
                "classification": "alta",
                "lux": 5400,
                "reliability": "medium",
                "source": "camera",
                "metadata": {"approximate": True},
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["garden_plant_id"] == garden_id
    assert payload["classification"] == "alta"
    assert payload["source"] == "camera"
    assert payload["metadata"] == {"approximate": True}

    async with session_factory() as session:
        saved = (await session.execute(select(light_measurements))).first()
    assert saved is not None


@pytest.mark.asyncio
async def test_create_light_measurement_rejects_other_users_garden_plant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await _create_user_garden_plant(session_factory, email="owner@example.com")
    _, other_garden_id = await _create_user_garden_plant(session_factory, email="other-light@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/light-measurements",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "garden_plant_id": other_garden_id,
                "classification": "media",
                "reliability": "low",
                "source": "manual",
            },
        )

    assert response.status_code == 404


async def _create_user_garden_plant(
    session_factory: async_sessionmaker[AsyncSession], *, email: str
) -> tuple[str, str]:
    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Ada", email, "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        profile_id = uuid4()
        garden_id = uuid4()
        await session.execute(
            insert(plant_profiles).values(
                id=profile_id,
                scientific_name=f"Nephrolepis {garden_id}",
                common_name="Helecho",
                aliases=[],
                sections={},
                sources=[],
                confidence=0.8,
                limitations=[],
            )
        )
        await session.execute(
            insert(garden_plants).values(
                id=garden_id,
                user_id=user.id,
                profile_id=profile_id,
                nickname="Helecho del living",
                custom_data={},
            )
        )
        await session.commit()

    return auth_session.token, str(garden_id)
