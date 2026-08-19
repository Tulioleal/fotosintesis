from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import garden_plants, light_measurements, plant_profiles, reminders
from app.main import app
from app.profile_garden.repository import PlantProfileGardenRepository
from app.schemas.reminders import ReminderStatus

NOW = datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_next_pending_reminder_summaries_selects_earliest_pending(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plant_id, _ = await _seed_garden(session_factory, email="next@example.com")
    later = await _insert_reminder(
        session_factory, user_id, plant_id, action="Fertilizar", due_at=NOW + timedelta(days=5)
    )
    earliest = await _insert_reminder(
        session_factory, user_id, plant_id, action="Regar", due_at=NOW + timedelta(days=1)
    )

    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        summaries = await repo.next_pending_reminder_summaries(
            user_id=user_id, plant_ids=[plant_id]
        )

    assert summaries[plant_id].action == "Regar"
    assert str(summaries[plant_id].id) == earliest
    assert str(later) not in {str(s.id) for s in summaries.values()}


@pytest.mark.asyncio
async def test_next_pending_reminder_summaries_excludes_completed_and_cancelled(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plant_id, _ = await _seed_garden(session_factory, email="exclude@example.com")
    await _insert_reminder(
        session_factory,
        user_id,
        plant_id,
        action="Regar",
        due_at=NOW + timedelta(days=1),
        status=ReminderStatus.completed,
    )
    await _insert_reminder(
        session_factory,
        user_id,
        plant_id,
        action="Podar",
        due_at=NOW + timedelta(days=2),
        status=ReminderStatus.cancelled,
    )

    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        summaries = await repo.next_pending_reminder_summaries(
            user_id=user_id, plant_ids=[plant_id]
        )

    assert plant_id not in summaries


@pytest.mark.asyncio
async def test_latest_light_summaries_selects_latest_measured(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plant_id, _ = await _seed_garden(session_factory, email="light-latest@example.com")
    await _insert_measurement(
        session_factory,
        user_id,
        plant_id,
        classification="baja",
        measured_at=NOW - timedelta(days=3),
    )
    await _insert_measurement(
        session_factory,
        user_id,
        plant_id,
        classification="alta",
        measured_at=NOW - timedelta(days=1),
    )

    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        summaries = await repo.latest_light_summaries(user_id=user_id, plant_ids=[plant_id])

    assert summaries[plant_id].classification.value == "alta"


@pytest.mark.asyncio
async def test_latest_light_summaries_returns_null_for_plants_without_measurements(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plant_id, _ = await _seed_garden(session_factory, email="light-empty@example.com")

    async with session_factory() as session:
        repo = PlantProfileGardenRepository(session)
        summaries = await repo.latest_light_summaries(user_id=user_id, plant_ids=[plant_id])

    assert plant_id not in summaries


@pytest.mark.asyncio
async def test_garden_list_and_detail_include_grounded_summaries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plant_id, token = await _seed_garden(session_factory, email="endpoint@example.com")
    await _insert_reminder(
        session_factory,
        user_id,
        plant_id,
        action="Regar",
        due_at=NOW + timedelta(days=1),
    )
    await _insert_measurement(
        session_factory,
        user_id,
        plant_id,
        classification="alta",
        measured_at=NOW - timedelta(days=1),
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/garden", headers=headers)
        detail = await client.get(f"/garden/{plant_id}", headers=headers)

    assert listing.status_code == 200
    list_item = listing.json()[0]
    assert list_item["next_reminder"]["action"] == "Regar"
    assert list_item["light_summary"]["classification"] == "alta"
    assert list_item["light_summary"]["source"] == "sensor"

    assert detail.status_code == 200
    assert detail.json()["next_reminder"]["id"] == list_item["next_reminder"]["id"]
    assert detail.json()["light_summary"]["id"] == list_item["light_summary"]["id"]


@pytest.mark.asyncio
async def test_garden_responses_return_null_summaries_without_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, plant_id, token = await _seed_garden(
        session_factory, email="null-summaries@example.com"
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        detail = await client.get(f"/garden/{plant_id}", headers=headers)

    assert detail.status_code == 200
    assert detail.json()["next_reminder"] is None
    assert detail.json()["light_summary"] is None


async def _seed_garden(
    session_factory: async_sessionmaker[AsyncSession], *, email: str
) -> tuple:
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
                scientific_name=f"Nephrolepis exaltata {email}",
                common_name="Helecho",
                aliases=[],
                sections={},
                sources=[],
                confidence=0.9,
                limitations=[],
            )
        )
        await session.execute(
            insert(garden_plants).values(
                id=garden_id,
                user_id=user.id,
                profile_id=profile_id,
                nickname="Helecho",
                custom_data={},
            )
        )
        await session.commit()
    return user.id, garden_id, auth_session.token


async def _insert_reminder(
    session_factory: async_sessionmaker[AsyncSession],
    user_id,
    garden_plant_id,
    *,
    action: str,
    due_at: datetime,
    status: ReminderStatus = ReminderStatus.pending,
) -> str:
    reminder_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=due_at,
                timezone="America/Argentina/Buenos_Aires",
                status=status.value,
            )
        )
        await session.commit()
    return str(reminder_id)


async def _insert_measurement(
    session_factory: async_sessionmaker[AsyncSession],
    user_id,
    garden_plant_id,
    *,
    classification: str,
    measured_at: datetime,
) -> str:
    measurement_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(light_measurements).values(
                id=measurement_id,
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                classification=classification,
                lux=500,
                reliability="medium",
                source="sensor",
                metadata={},
                measured_at=measured_at,
            )
        )
        await session.commit()
    return str(measurement_id)
