from datetime import date, time, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import garden_plants, plant_profiles
from app.main import app
from app.reminders.repository import ReminderRepository
from app.schemas.reminders import ReminderCreate, ReminderRecurrence, ReminderStatus, ReminderUpdate


@pytest.mark.asyncio
async def test_reminder_routes_support_authenticated_crud_flow(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="routes@example.com"
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = _reminder_payload(garden_plant_id, action="Regar", recurrence="weekly")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/reminders", json=payload, headers=headers)
        reminder_id = created.json()["id"]
        listed = await client.get("/reminders", headers=headers)
        filtered = await client.get(f"/reminders?garden_plant_id={garden_plant_id}", headers=headers)
        updated = await client.patch(
            f"/reminders/{reminder_id}",
            json={"action": "Fertilizar", "recurrence": "none"},
            headers=headers,
        )
        completed = await client.post(f"/reminders/{reminder_id}/complete", headers=headers)
        deleted = await client.delete(f"/reminders/{reminder_id}", headers=headers)

    assert created.status_code == 201
    assert created.json()["action"] == "Regar"
    assert created.json()["plant_name"] == "Helecho"
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [reminder_id]
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [reminder_id]
    assert updated.status_code == 200
    assert updated.json()["action"] == "Fertilizar"
    assert updated.json()["recurrence"] == "none"
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert deleted.status_code == 200
    assert deleted.json() == {"status": "deleted"}


@pytest.mark.asyncio
async def test_reminder_routes_enforce_ownership_validation_and_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="owner@example.com"
    )
    _, _, other_garden_plant_id = await _create_user_garden(
        session_factory, email="other@example.com"
    )
    headers = {"Authorization": f"Bearer {token}"}
    missing_reminder_id = uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        past_due = await client.post(
            "/reminders",
            json={
                "garden_plant_id": str(garden_plant_id),
                "action": "Regar",
                "date": "2000-01-01",
                "time": "09:00:00",
                "recurrence": "none",
            },
            headers=headers,
        )
        wrong_plant = await client.post(
            "/reminders",
            json=_reminder_payload(other_garden_plant_id, action="Regar"),
            headers=headers,
        )
        missing_update = await client.patch(
            f"/reminders/{missing_reminder_id}", json={"action": "Regar"}, headers=headers
        )
        missing_complete = await client.post(
            f"/reminders/{missing_reminder_id}/complete", headers=headers
        )
        missing_delete = await client.delete(f"/reminders/{missing_reminder_id}", headers=headers)

    assert past_due.status_code == 422
    assert past_due.json()["detail"] == "La fecha y hora deben ser futuras."
    assert wrong_plant.status_code == 404
    assert wrong_plant.json()["detail"] == "Planta no encontrada en Mi Jardin."
    assert missing_update.status_code == 404
    assert missing_complete.status_code == 404
    assert missing_delete.status_code == 404


@pytest.mark.asyncio
async def test_reminder_routes_reject_unauthenticated_access() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/reminders")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_repository_creates_lists_filters_and_counts_active_reminders(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="repo-create@example.com"
    )
    _, _, other_garden_plant_id = await _create_user_garden(
        session_factory, email="repo-other-filter@example.com"
    )

    async with session_factory() as session:
        repository = ReminderRepository(session)
        later = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(garden_plant_id, action="Fertilizar", days=2),
        )
        earlier = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(garden_plant_id, action="Regar", days=1),
        )
        wrong_filter = await repository.list_reminders(
            user_id=user_id, garden_plant_id=other_garden_plant_id
        )
        listed = await repository.list_reminders(user_id=user_id)
        active_count = await _active_reminders(session, garden_plant_id)

    assert later is not None
    assert earlier is not None
    assert wrong_filter == []
    assert [item.action for item in listed] == ["Regar", "Fertilizar"]
    assert listed[0].plant_name == "Helecho"
    assert active_count == 2


@pytest.mark.asyncio
async def test_repository_enforces_garden_ownership(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="repo-owner@example.com"
    )
    _, _, other_garden_plant_id = await _create_user_garden(
        session_factory, email="repo-not-owner@example.com"
    )

    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Regar")
        )
        denied_create = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(other_garden_plant_id, action="Regar")
        )
        denied_update = await repository.update_reminder(
            user_id=user_id,
            reminder_id=created.id,
            payload=ReminderUpdate(garden_plant_id=other_garden_plant_id),
        )
        unchanged = await repository.get_reminder(user_id=user_id, reminder_id=created.id)

    assert created is not None
    assert denied_create is None
    assert denied_update is None
    assert unchanged is not None
    assert unchanged.garden_plant_id == garden_plant_id


@pytest.mark.asyncio
async def test_repository_updates_partial_fields_and_preserves_omitted_values(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="repo-update@example.com"
    )

    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(
                garden_plant_id,
                action="Regar",
                recurrence=ReminderRecurrence.weekly,
                suggestion="Sugerido",
            ),
        )
        updated = await repository.update_reminder(
            user_id=user_id,
            reminder_id=created.id,
            payload=ReminderUpdate(action="  Fertilizar  "),
        )

    assert updated is not None
    assert updated.action == "Fertilizar"
    assert updated.garden_plant_id == garden_plant_id
    assert updated.recurrence == ReminderRecurrence.weekly
    assert updated.suggestion_justification == "Sugerido"


@pytest.mark.asyncio
async def test_repository_deletes_pending_reminders_and_handles_missing_records(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="repo-delete@example.com"
    )

    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Regar")
        )
        deleted = await repository.delete_reminder(user_id=user_id, reminder_id=created.id)
        deleted_again = await repository.delete_reminder(user_id=user_id, reminder_id=created.id)
        active_count = await _active_reminders(session, garden_plant_id)

    assert deleted is True
    assert deleted_again is False
    assert active_count == 0


@pytest.mark.asyncio
async def test_repository_completes_non_recurring_and_recurring_reminders(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="repo-complete@example.com"
    )

    async with session_factory() as session:
        repository = ReminderRepository(session)
        one_time = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Regar")
        )
        completed_one_time = await repository.complete_reminder(
            user_id=user_id, reminder_id=one_time.id
        )
        recurring = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(
                garden_plant_id, action="Fertilizar", recurrence=ReminderRecurrence.weekly
            ),
        )
        completed_recurring = await repository.complete_reminder(
            user_id=user_id, reminder_id=recurring.id
        )
        completed_again = await repository.complete_reminder(
            user_id=user_id, reminder_id=recurring.id
        )
        missing = await repository.complete_reminder(user_id=user_id, reminder_id=uuid4())
        listed = await repository.list_reminders(user_id=user_id)
        active_count = await _active_reminders(session, garden_plant_id)

    assert completed_one_time is not None
    assert completed_one_time.status == ReminderStatus.completed
    assert completed_one_time.next_occurrence_at is None
    assert completed_recurring is not None
    assert completed_recurring.status == ReminderStatus.completed
    assert completed_recurring.next_occurrence_at is not None
    assert completed_again is not None
    assert completed_again.id == recurring.id
    assert missing is None
    assert [item.status for item in listed].count(ReminderStatus.pending) == 1
    assert active_count == 1


async def _create_user_garden(
    session_factory: async_sessionmaker[AsyncSession], *, email: str
) -> tuple[str, UUID, UUID]:
    async with session_factory() as session:
        auth_repository = DatabaseAuthRepository(session)
        user = await auth_repository.create_user("Ada", email, "password123")
        auth_session = await auth_repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        profile_id = uuid4()
        garden_plant_id = uuid4()
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
                id=garden_plant_id,
                user_id=user.id,
                profile_id=profile_id,
                nickname="Helecho",
                notes="Pulverizar hojas",
                location="Balcon",
                custom_data={},
            )
        )
        await session.commit()
    return auth_session.token, user.id, garden_plant_id


def _reminder_payload(
    garden_plant_id: UUID, *, action: str, recurrence: str = "none"
) -> dict[str, str]:
    due = date.today() + timedelta(days=1)
    return {
        "garden_plant_id": str(garden_plant_id),
        "action": action,
        "date": due.isoformat(),
        "time": "09:00:00",
        "recurrence": recurrence,
    }


def _create_payload(
    garden_plant_id: UUID,
    *,
    action: str,
    days: int = 1,
    recurrence: ReminderRecurrence = ReminderRecurrence.none,
    suggestion: str | None = None,
) -> ReminderCreate:
    return ReminderCreate(
        garden_plant_id=garden_plant_id,
        action=action,
        date=date.today() + timedelta(days=days),
        time=time(9, 0),
        recurrence=recurrence,
        suggestion_justification=suggestion,
    )


async def _active_reminders(session: AsyncSession, garden_plant_id: UUID) -> int:
    return await session.scalar(
        select(garden_plants.c.active_reminders).where(garden_plants.c.id == garden_plant_id)
    )
