from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import garden_plants, plant_profiles, reminders
from app.main import app
from app.reminders.repository import ReminderRepository
from app.schemas.reminders import ReminderCreate, ReminderRecurrence, ReminderStatus, ReminderUpdate

USER_TIMEZONE = "America/Argentina/Buenos_Aires"


@pytest.mark.asyncio
async def test_reminder_routes_support_authenticated_crud_flow(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="routes@example.com"
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = _reminder_payload(garden_plant_id, action="Water", recurrence="weekly")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/reminders", json=payload, headers=headers)
        reminder_id = created.json()["id"]
        listed = await client.get("/reminders", headers=headers)
        filtered = await client.get(f"/reminders?garden_plant_id={garden_plant_id}", headers=headers)
        updated = await client.patch(
            f"/reminders/{reminder_id}",
            json={"action": "Fertilize", "recurrence": "none"},
            headers=headers,
        )
        completed = await client.post(f"/reminders/{reminder_id}/complete", headers=headers)
        deleted = await client.delete(f"/reminders/{reminder_id}", headers=headers)

    assert created.status_code == 201
    assert created.json()["action"] == "Water"
    assert created.json()["plant_name"] == "Helecho"
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [reminder_id]
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [reminder_id]
    assert updated.status_code == 200
    assert updated.json()["action"] == "Fertilize"
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
                "action": "Water",
                "date": "2000-01-01",
                "time": "09:00:00",
                "recurrence": "none",
            },
            headers=headers,
        )
        wrong_plant = await client.post(
            "/reminders",
            json=_reminder_payload(other_garden_plant_id, action="Water"),
            headers=headers,
        )
        missing_update = await client.patch(
            f"/reminders/{missing_reminder_id}", json={"action": "Water"}, headers=headers
        )
        missing_complete = await client.post(
            f"/reminders/{missing_reminder_id}/complete", headers=headers
        )
        missing_delete = await client.delete(f"/reminders/{missing_reminder_id}", headers=headers)

    assert past_due.status_code == 422
    assert past_due.json()["detail"] == "The date and time must be in the future."
    assert wrong_plant.status_code == 404
    assert wrong_plant.json()["detail"] == "Plant not found in My Garden."
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
            payload=_create_payload(garden_plant_id, action="Fertilize", days=2),
        )
        earlier = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(garden_plant_id, action="Water", days=1),
        )
        wrong_filter = await repository.list_reminders(
            user_id=user_id, garden_plant_id=other_garden_plant_id
        )
        listed = await repository.list_reminders(user_id=user_id)
        active_count = await _active_reminders(session, garden_plant_id)

    assert later is not None
    assert earlier is not None
    assert wrong_filter == []
    assert [item.action for item in listed] == ["Water", "Fertilize"]
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
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Water")
        )
        denied_create = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(other_garden_plant_id, action="Water")
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
                action="Water",
                recurrence=ReminderRecurrence.weekly,
                suggestion="Suggested",
            ),
        )
        updated = await repository.update_reminder(
            user_id=user_id,
            reminder_id=created.id,
            payload=ReminderUpdate(action="  Fertilize  "),
        )

    assert updated is not None
    assert updated.action == "Fertilize"
    assert updated.garden_plant_id == garden_plant_id
    assert updated.recurrence == ReminderRecurrence.weekly
    assert updated.suggestion_justification == "Suggested"


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
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Water")
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
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Water")
        )
        completed_one_time = await repository.complete_reminder(
            user_id=user_id, reminder_id=one_time.id
        )
        recurring = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(
                garden_plant_id, action="Fertilize", recurrence=ReminderRecurrence.weekly
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


@pytest.mark.asyncio
async def test_reminder_timezone_override_wins_over_user_preference(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="tz-override@example.com"
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(
                garden_plant_id,
                action="Water",
                timezone="America/New_York",
            ),
        )

    assert created is not None
    assert created.timezone == "America/New_York"
    ny = ZoneInfo("America/New_York")
    assert _aware_utc(created.due_at).astimezone(ny).hour == 9


@pytest.mark.asyncio
async def test_reminder_update_resolves_new_due_at_in_effective_timezone(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="update-tz@example.com"
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id,
            payload=_create_payload(
                garden_plant_id,
                action="Water",
                timezone="America/New_York",
            ),
        )
        updated = await repository.update_reminder(
            user_id=user_id,
            reminder_id=created.id,
            payload=ReminderUpdate(
                date=date(2026, 12, 1),
                time=time(8, 45),
                timezone="America/New_York",
            ),
        )

    assert updated is not None
    assert updated.timezone == "America/New_York"
    ny = ZoneInfo("America/New_York")
    local = _aware_utc(updated.due_at).astimezone(ny)
    assert local.year == 2026 and local.month == 12 and local.day == 1
    assert local.hour == 8 and local.minute == 45


@pytest.mark.asyncio
async def test_reminder_missing_effective_timezone_returns_422(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="no-tz@example.com", timezone=None
    )
    headers = {"Authorization": f"Bearer {token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/reminders", json=_reminder_payload(garden_plant_id, action="Water"), headers=headers
        )

    assert response.status_code == 422
    assert "timezone" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reminder_invalid_timezone_returns_422(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="invalid-tz@example.com"
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = _reminder_payload(garden_plant_id, action="Water")
    payload["timezone"] = "Not/A_Zone"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/reminders", json=payload, headers=headers)

    assert response.status_code == 422
    assert "timezone" in str(response.json()["detail"]).lower()


@pytest.mark.asyncio
async def test_reminder_nonexistent_local_time_returns_recoverable_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="gap@example.com", timezone="America/New_York"
    )
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "garden_plant_id": str(garden_plant_id),
        "action": "Water",
        "date": "2026-03-08",
        "time": "02:30:00",
        "recurrence": "none",
        "timezone": "America/New_York",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/reminders", json=payload, headers=headers)

    assert response.status_code == 422
    assert "daylight saving" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reminder_ambiguous_local_time_resolves_to_earlier_offset(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="fold@example.com", timezone="America/New_York"
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id,
            payload=ReminderCreate(
                garden_plant_id=garden_plant_id,
                action="Water",
                date=date(2026, 11, 1),
                time=time(1, 30),
                recurrence=ReminderRecurrence.none,
                timezone="America/New_York",
            ),
        )

    assert created is not None
    ny = ZoneInfo("America/New_York")
    local_back = _aware_utc(created.due_at).astimezone(ny)
    assert local_back.hour == 1 and local_back.minute == 30
    assert local_back.utcoffset() == timedelta(hours=-4)


@pytest.mark.asyncio
async def test_recurring_reminder_preserves_local_time_across_dst(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="dst@example.com", timezone="America/New_York"
    )
    reminder_id = await _insert_reminder(
        session_factory,
        user_id=user_id,
        garden_plant_id=garden_plant_id,
        action="Water",
        due_at="2026-03-05T14:00:00Z",
        recurrence=ReminderRecurrence.weekly,
        timezone="America/New_York",
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        completed = await repository.complete_reminder(user_id=user_id, reminder_id=reminder_id)

    assert completed is not None
    assert completed.next_occurrence_at is not None
    ny = ZoneInfo("America/New_York")
    next_local = _aware_utc(completed.next_occurrence_at).astimezone(ny)
    assert next_local.hour == 9


@pytest.mark.asyncio
async def test_monthly_reminder_clamps_day_in_local_time(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="monthly@example.com", timezone="America/New_York"
    )
    reminder_id = await _insert_reminder(
        session_factory,
        user_id=user_id,
        garden_plant_id=garden_plant_id,
        action="Water",
        due_at="2026-01-31T14:00:00Z",
        recurrence=ReminderRecurrence.monthly,
        timezone="America/New_York",
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        completed = await repository.complete_reminder(user_id=user_id, reminder_id=reminder_id)

    assert completed is not None
    assert completed.next_occurrence_at is not None
    ny = ZoneInfo("America/New_York")
    next_local = _aware_utc(completed.next_occurrence_at).astimezone(ny)
    assert next_local.month == 2
    assert next_local.day == 28


@pytest.mark.asyncio
async def test_moving_pending_reminder_updates_both_counters_transactionally(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, source_plant = await _create_user_garden(
        session_factory, email="move-src@example.com"
    )
    destination_plant = await _add_plant_for_user(
        session_factory, user_id=user_id, label="Destino"
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(source_plant, action="Water")
        )
        moved = await repository.update_reminder(
            user_id=user_id,
            reminder_id=created.id,
            payload=ReminderUpdate(garden_plant_id=destination_plant),
        )
        source_count = await _active_reminders(session, source_plant)
        destination_count = await _active_reminders(session, destination_plant)

    assert moved is not None
    assert moved.garden_plant_id == destination_plant
    assert source_count == 0
    assert destination_count == 1


@pytest.mark.asyncio
async def test_moving_completed_reminder_does_not_change_counters(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, source_plant = await _create_user_garden(
        session_factory, email="move-complete@example.com"
    )
    destination_plant = await _add_plant_for_user(
        session_factory, user_id=user_id, label="Destino"
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        created = await repository.create_reminder(
            user_id=user_id, payload=_create_payload(source_plant, action="Water")
        )
        await repository.complete_reminder(user_id=user_id, reminder_id=created.id)
        moved = await repository.update_reminder(
            user_id=user_id,
            reminder_id=created.id,
            payload=ReminderUpdate(garden_plant_id=destination_plant),
        )
        source_count = await _active_reminders(session, source_plant)
        destination_count = await _active_reminders(session, destination_plant)

    assert moved is not None
    assert source_count == 0
    assert destination_count == 0


@pytest.mark.asyncio
async def test_reconciliation_backfill_repairs_stored_counters(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="reconcile@example.com"
    )
    async with session_factory() as session:
        repository = ReminderRepository(session)
        await repository.create_reminder(
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Water")
        )
        await repository.create_reminder(
            user_id=user_id, payload=_create_payload(garden_plant_id, action="Fertilize")
        )
        await session.execute(
            update(garden_plants)
            .where(garden_plants.c.id == garden_plant_id)
            .values(active_reminders=99)
        )
        await session.commit()

    async with session_factory() as session:
        repository = ReminderRepository(session)
        changed = await repository.reconcile_active_reminders()
        repaired = await _active_reminders(session, garden_plant_id)

    assert changed >= 1
    assert repaired == 2


async def _insert_reminder(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    garden_plant_id: UUID,
    action: str,
    due_at: str,
    recurrence: ReminderRecurrence,
    timezone: str,
) -> UUID:
    reminder_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=datetime.fromisoformat(due_at),
                recurrence=recurrence.value if recurrence != ReminderRecurrence.none else None,
                suggestion_justification=None,
                timezone=timezone,
                status=ReminderStatus.pending.value,
            )
        )
        await session.execute(
            update(garden_plants)
            .where(garden_plants.c.id == garden_plant_id)
            .values(active_reminders=garden_plants.c.active_reminders + 1)
        )
        await session.commit()
    return reminder_id


async def _create_user_garden(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    timezone: str | None = USER_TIMEZONE,
) -> tuple[str, UUID, UUID]:
    async with session_factory() as session:
        auth_repository = DatabaseAuthRepository(session)
        user = await auth_repository.create_user("Ada", email, "password123")
        if timezone is not None:
            await auth_repository.update_timezone(user.id, timezone)
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
                notes="Mist the leaves",
                location="Balcony",
                custom_data={},
            )
        )
        await session.commit()
    return auth_session.token, user.id, garden_plant_id


async def _add_plant_for_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    label: str,
) -> UUID:
    async with session_factory() as session:
        profile_id = uuid4()
        garden_plant_id = uuid4()
        await session.execute(
            insert(plant_profiles).values(
                id=profile_id,
                scientific_name=f"Nephrolepis exaltata {label}",
                common_name=label,
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
                user_id=user_id,
                profile_id=profile_id,
                nickname=label,
                notes=None,
                location=None,
                custom_data={},
            )
        )
        await session.commit()
    return garden_plant_id


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
    timezone: str | None = None,
) -> ReminderCreate:
    return ReminderCreate(
        garden_plant_id=garden_plant_id,
        action=action,
        date=date.today() + timedelta(days=days),
        time=time(9, 0),
        recurrence=recurrence,
        suggestion_justification=suggestion,
        timezone=timezone,
    )


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


async def _active_reminders(session: AsyncSession, garden_plant_id: UUID) -> int:
    return await session.scalar(
        select(garden_plants.c.active_reminders).where(garden_plants.c.id == garden_plant_id)
    )
