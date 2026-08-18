from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import DatabaseAuthRepository
from app.auth.tables import garden_plants, light_measurements, plant_profiles, reminders
from app.reminders.repository import ReminderRepository
from app.reminders.suggestions import (
    PlantNotFoundError,
    ProviderFailureError,
    ReminderSuggestionService,
)
from app.schemas.reminders import (
    ReminderClarificationResult,
    ReminderCreate,
    ReminderDuplicateResult,
    ReminderRecurrence,
    ReminderSuggestionRequest,
    ReminderSuggestionResult,
)
from app.assistant.tools import ToolResult

USER_TIMEZONE = "America/Argentina/Buenos_Aires"


async def _create_user_garden(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str,
    timezone: str | None = USER_TIMEZONE,
    sections: dict | None = None,
    notes: str | None = "Mist the leaves daily",
) -> tuple[UUID, UUID]:
    async with session_factory() as session:
        auth_repository = DatabaseAuthRepository(session)
        user = await auth_repository.create_user("Ada", email, "password123")
        if timezone is not None:
            await auth_repository.update_timezone(user.id, timezone)
        profile_id = uuid4()
        garden_plant_id = uuid4()
        await session.execute(
            insert(plant_profiles).values(
                id=profile_id,
                scientific_name=f"Nephrolepis exaltata {email}",
                common_name="Helecho",
                aliases=[],
                sections=sections or {"care": ["Riego moderado"]},
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
                notes=notes,
                location="Balcony",
                custom_data={},
            )
        )
        await session.commit()
    return user.id, garden_plant_id


async def _insert_reminder(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: UUID,
    garden_plant_id: UUID,
    action: str,
    due_at: datetime,
    recurrence: str,
) -> UUID:
    reminder_id = uuid4()
    async with session_factory() as session:
        await session.execute(
            insert(reminders).values(
                id=reminder_id,
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                action=action,
                due_at=due_at,
                recurrence=recurrence,
                status="pending",
                suggestion_justification=None,
                timezone=USER_TIMEZONE,
            )
        )
        await session.commit()
    return reminder_id


def _classify_data(action: str = "Riego", *, light: bool = False, confidence: float = 0.92):
    return {
        "action": action,
        "light_context_relevant": light,
        "confidence": confidence,
        "limitations": [],
    }


def _suggestion_data(
    *,
    date_value: str | None = "2999-01-10",
    time_value: str | None = "09:00",
    timezone_value: str | None = USER_TIMEZONE,
    recurrence: str | None = "weekly",
    justification: str = "Basado en el perfil y el contexto guardado.",
):
    return {
        "date": date_value,
        "time": time_value,
        "timezone": timezone_value,
        "recurrence": recurrence,
        "justification": justification,
    }


def _make_generate_json(classifier: dict, suggestion: dict):
    """Return a generate_json fake that dispatches on the schema shape."""

    async def fake_generate_json(prompt: str, schema: dict, **kwargs) -> ToolResult:
        if "action" in schema.get("properties", {}):
            return ToolResult(ok=True, data=dict(classifier))
        return ToolResult(ok=True, data=dict(suggestion))

    return fake_generate_json


def _make_service(
    session: AsyncSession, classifier: dict, suggestion: dict
) -> ReminderSuggestionService:
    service = ReminderSuggestionService(session)
    service.tools.generate_json = _make_generate_json(classifier, suggestion)
    return service


@pytest.mark.asyncio
async def test_complete_suggestion_returns_evidence_confidence_and_justification(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="suggest@example.com"
    )
    async with session_factory() as session:
        service = _make_service(
            session,
            _classify_data("Riego"),
            _suggestion_data(),
        )
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderSuggestionResult)
    assert outcome.kind == "suggestion"
    assert outcome.action == "Riego"
    assert outcome.garden_plant_id == garden_plant_id
    assert outcome.plant_name == "Helecho"
    assert outcome.date == date(2999, 1, 10)
    assert outcome.time == time(9, 0)
    assert outcome.timezone == USER_TIMEZONE
    assert outcome.recurrence == ReminderRecurrence.weekly
    assert outcome.confidence == 0.92
    assert outcome.evidence.taxonomy is not None
    assert outcome.evidence.notes == "Mist the leaves daily"
    assert outcome.evidence.location == "Balcony"
    assert outcome.evidence.active_reminders == 0
    assert outcome.justification


@pytest.mark.asyncio
async def test_missing_schedule_fields_return_clarification_without_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="clarify@example.com"
    )
    async with session_factory() as session:
        service = _make_service(
            session,
            _classify_data("Riego"),
            _suggestion_data(
                date_value=None,
                time_value=None,
                recurrence=None,
                timezone_value=None,
            ),
        )
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderClarificationResult)
    assert outcome.kind == "clarification"
    assert set(outcome.missing_fields) == {"date", "time", "timezone", "recurrence"}


@pytest.mark.asyncio
async def test_duplicate_returns_existing_reference(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="dupe@example.com"
    )
    existing = await _insert_reminder(
        session_factory,
        user_id=user_id,
        garden_plant_id=garden_plant_id,
        action="Riego",
        due_at=datetime(2999, 1, 10, 9, 0, tzinfo=timezone.utc),
        recurrence="weekly",
    )
    async with session_factory() as session:
        service = _make_service(session, _classify_data("Riego"), _suggestion_data())
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderDuplicateResult)
    assert outcome.kind == "duplicate"
    assert outcome.existing_reminder_id == existing


@pytest.mark.asyncio
async def test_insufficient_evidence_returns_limitations_on_suggestion(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="limited@example.com"
    )
    async with session_factory() as session:
        classifier = _classify_data("Riego", confidence=0.4)
        classifier["limitations"] = ["Limited evidence available."]
        service = _make_service(session, classifier, _suggestion_data())
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderSuggestionResult)
    assert outcome.confidence == 0.4
    assert outcome.limitations == ["Limited evidence available."]


@pytest.mark.asyncio
async def test_provider_failure_raises_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="fail@example.com"
    )
    async with session_factory() as session:
        service = ReminderSuggestionService(session)

        async def failing(prompt: str, schema: dict, **kwargs) -> ToolResult:
            return ToolResult(ok=False, error="model_generate_json failed")

        service.tools.generate_json = failing
        with pytest.raises(ProviderFailureError):
            await service.suggest(
                user_id=user_id,
                payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
            )


@pytest.mark.asyncio
async def test_missing_plant_raises_not_found(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, _ = await _create_user_garden(session_factory, email="owner@example.com")
    async with session_factory() as session:
        service = _make_service(session, _classify_data("Riego"), _suggestion_data())
        with pytest.raises(PlantNotFoundError):
            await service.suggest(
                user_id=user_id,
                payload=ReminderSuggestionRequest(
                    garden_plant_id=uuid4(), request=""
                ),
            )


@pytest.mark.asyncio
async def test_regression_no_fixed_calendar_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """AI-labeled suggestions must not originate from tomorrow, 09:00, or weekly."""
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="regression@example.com"
    )
    async with session_factory() as session:
        service = _make_service(
            session,
            _classify_data("Poda"),
            _suggestion_data(
                date_value="2999-03-15",
                time_value="18:30",
                recurrence="monthly",
                timezone_value="America/Montevideo",
            ),
        )
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderSuggestionResult)
    assert outcome.action == "Poda"
    assert outcome.date == date(2999, 3, 15)
    assert outcome.time == time(18, 30)
    assert outcome.recurrence == ReminderRecurrence.monthly
    assert outcome.timezone == "America/Montevideo"


@pytest.mark.asyncio
async def test_regression_non_english_evidence_uses_model_output_not_keywords(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Non-English or paraphrased evidence reaches semantic judging without
    keyword matches; the action comes from the model's schema-validated output."""
    user_id, garden_plant_id = await _create_user_garden(
        session_factory,
        email="multilang@example.com",
        sections={"care": ["Zorg voor de bladeren", "Bewässerung"]},
        notes="Bitte giessen",
    )
    captured: list[str] = []
    async with session_factory() as session:
        service = ReminderSuggestionService(session)

        async def capturing(prompt: str, schema: dict, **kwargs) -> ToolResult:
            captured.append(prompt)
            if "action" in schema.get("properties", {}):
                return ToolResult(
                    ok=True,
                    data={
                        "action": "Gießen",
                        "light_context_relevant": False,
                        "confidence": 0.8,
                        "limitations": [],
                    },
                )
            return ToolResult(ok=True, data=_suggestion_data())

        service.tools.generate_json = capturing
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderSuggestionResult)
    assert outcome.action == "Gießen"
    action_prompt = captured[0]
    assert "Zorg voor de bladeren" in action_prompt
    assert "Bitte giessen" in action_prompt


@pytest.mark.asyncio
async def test_light_context_loaded_only_when_semantically_relevant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="light@example.com"
    )
    async with session_factory() as session:
        await session.execute(
            insert(light_measurements).values(
                id=uuid4(),
                user_id=user_id,
                garden_plant_id=garden_plant_id,
                source="sensor",
                classification="bright_indirect",
                lux=800,
                reliability="high",
                measured_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    async with session_factory() as session:
        service = _make_service(
            session,
            _classify_data("Riego", light=True),
            _suggestion_data(),
        )
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderSuggestionResult)
    assert outcome.evidence.light_context
    assert "bright_indirect" in outcome.evidence.light_context


@pytest.mark.asyncio
async def test_create_reminder_rechecks_duplicate_transactionally(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="txdupe@example.com"
    )
    due = date.today() + timedelta(days=1)
    payload = ReminderCreate(
        garden_plant_id=garden_plant_id,
        action="Riego",
        date=due,
        time=time(9, 0),
        recurrence=ReminderRecurrence.weekly,
        timezone=USER_TIMEZONE,
    )
    async with session_factory() as session:
        repo = ReminderRepository(session)
        first = await repo.create_reminder(user_id=user_id, payload=payload)
        assert first is not None
        first_id = first.id

    async with session_factory() as session:
        repo = ReminderRepository(session)
        second = await repo.create_reminder(user_id=user_id, payload=payload)
        assert second is not None
        assert second.id == first_id

    async with session_factory() as session:
        count = await session.scalar(
            select(reminders.c.id)
            .where(reminders.c.garden_plant_id == garden_plant_id)
        )
    assert count is not None


@pytest.mark.asyncio
async def test_create_reminder_allows_distinct_schedule(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="distinct@example.com"
    )
    due = date.today() + timedelta(days=1)
    first = ReminderCreate(
        garden_plant_id=garden_plant_id,
        action="Riego",
        date=due,
        time=time(9, 0),
        recurrence=ReminderRecurrence.weekly,
        timezone=USER_TIMEZONE,
    )
    second = ReminderCreate(
        garden_plant_id=garden_plant_id,
        action="Fertilizante",
        date=due,
        time=time(18, 0),
        recurrence=ReminderRecurrence.weekly,
        timezone=USER_TIMEZONE,
    )
    async with session_factory() as session:
        repo = ReminderRepository(session)
        first_result = await repo.create_reminder(user_id=user_id, payload=first)
        second_result = await repo.create_reminder(user_id=user_id, payload=second)
    assert first_result is not None
    assert second_result is not None
    assert first_result.id != second_result.id


@pytest.mark.asyncio
async def test_light_context_not_loaded_when_irrelevant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user_id, garden_plant_id = await _create_user_garden(
        session_factory, email="nolight@example.com"
    )
    async with session_factory() as session:
        service = _make_service(
            session,
            _classify_data("Riego", light=False),
            _suggestion_data(),
        )
        outcome = await service.suggest(
            user_id=user_id,
            payload=ReminderSuggestionRequest(garden_plant_id=garden_plant_id, request=""),
        )

    assert isinstance(outcome, ReminderSuggestionResult)
    assert outcome.evidence.light_context is None
