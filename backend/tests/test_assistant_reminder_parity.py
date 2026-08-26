"""Parity tests: assistant chat reminder creation enforces the same rules as
the manual reminders API (future-date, effective timezone, duplicates)."""

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.assistant.repository import AssistantRepository
from app.assistant.tools import AssistantTools
from app.auth.tables import reminders
from app.knowledge.repository import KnowledgeRepository
from app.main import app

USER_TIMEZONE = "America/Argentina/Buenos_Aires"


@pytest.mark.asyncio
async def test_chat_create_rejects_past_due_with_same_message_as_api(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _, garden_plant_id = await _create_user_garden(
        session_factory, email="parity-past@example.com"
    )

    tools = _tools(session_factory)
    zone = ZoneInfo(USER_TIMEZONE)
    result = await tools.reminder_create(
        user_id=await _user_id(session_factory, "parity-past@example.com"),
        garden_plant_id=garden_plant_id,
        action="Water",
        due_at=datetime(2020, 1, 1, 10, 30, tzinfo=zone),
        recurrence="weekly",
        justification="chat",
        timezone=USER_TIMEZONE,
    )
    assert result.ok is False
    assert result.error == "The date and time must be in the future."

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        api_response = await client.post(
            "/reminders",
            json={
                "garden_plant_id": str(garden_plant_id),
                "action": "Water",
                "date": "2020-01-01",
                "time": "10:30:00",
                "recurrence": "weekly",
                "timezone": USER_TIMEZONE,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert api_response.status_code == 422
    assert api_response.json()["detail"] == result.error


@pytest.mark.asyncio
async def test_chat_create_returns_existing_duplicate_without_inserting(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="parity-dup@example.com"
    )
    zone = ZoneInfo(USER_TIMEZONE)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/reminders",
            json={
                "garden_plant_id": str(garden_plant_id),
                "action": "Water",
                "date": "2099-06-01",
                "time": "10:30:00",
                "recurrence": "weekly",
                "timezone": USER_TIMEZONE,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert created.status_code == 201

    tools = _tools(session_factory)
    result = await tools.reminder_create(
        user_id=user_id,
        garden_plant_id=garden_plant_id,
        action="water",
        due_at=datetime(2099, 6, 1, 10, 30, tzinfo=zone),
        recurrence="weekly",
        justification="chat",
        timezone=USER_TIMEZONE,
    )

    assert result.ok is True
    assert result.data["duplicate"] is True
    async with session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(reminders))
    assert total == 1


@pytest.mark.asyncio
async def test_chat_create_resolves_stored_user_timezone_when_unset(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="parity-tz@example.com"
    )
    tools = _tools(session_factory)
    result = await tools.reminder_create(
        user_id=user_id,
        garden_plant_id=garden_plant_id,
        action="Water",
        # Naive wall-clock 10:30 in the stored ART zone == 13:30Z.
        due_at=datetime(2099, 6, 1, 10, 30),
        recurrence="weekly",
        justification="chat",
        timezone=None,
    )

    assert result.ok is True, result.error
    async with session_factory() as session:
        row = (
            await session.execute(select(reminders.c.due_at, reminders.c.timezone))
        ).first()
    assert row.timezone == USER_TIMEZONE
    assert row.due_at.hour == 13 and row.due_at.minute == 30


def test_classifier_contract_declares_and_prompts_reminder_fields() -> None:
    from app.assistant.graph.classifier import CARE_CLASSIFIER_SCHEMA, _care_classifier_prompt

    properties = CARE_CLASSIFIER_SCHEMA["properties"]
    for field in (
        "reminder_action",
        "reminder_recurrence",
        "reminder_due_at",
        "reminder_suggestion_requested",
    ):
        assert field in properties, field
    assert "reminder_due_at" not in CARE_CLASSIFIER_SCHEMA["required"]
    prompt = _care_classifier_prompt({"message": "x", "plant_hint": None})
    assert "reminder_request" in prompt
    assert "reminder_suggestion_requested" in prompt


def test_assistant_tools_use_the_shared_validation_core() -> None:
    import inspect

    from app.assistant.tools import facade as tools_facade
    from app.reminders import validation as shared

    source = inspect.getsource(tools_facade.AssistantTools.reminder_create)
    assert "ensure_future_due" in source
    assert shared.ensure_future_due is not None


def _tools(session_factory: async_sessionmaker[AsyncSession]) -> AssistantTools:
    """One open session shared by the assistant facade and ReminderRepository,
    mirroring production where both wrap the request session."""
    session = session_factory()
    return AssistantTools(
        AssistantRepository(session),
        KnowledgeRepository(session),
    )


async def _user_id(session_factory: async_sessionmaker[AsyncSession], email: str):
    from sqlalchemy import select

    from app.auth.tables import users

    async with session_factory() as session:
        row = (await session.execute(select(users.c.id).where(users.c.email == email))).first()
        return row[0]


# Re-exported fixture helper from the reminders suite to avoid duplication.
from tests.test_reminders import _create_user_garden  # noqa: E402,F401
