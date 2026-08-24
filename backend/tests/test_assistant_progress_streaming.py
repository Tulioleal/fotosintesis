"""SSE chat progress stream: closed vocabulary, ordering, single terminal
event, and structural redaction of internal content."""

import json
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.assistant.streaming import (
    HEARTBEAT_FRAME,
    STAGE_LABELS_ES,
    StageSequence,
    build_error_event,
    build_stage_event,
    sse_frame,
)
from tests._assistant_helpers import FakeTools


def test_stage_events_use_closed_vocabulary_and_whitelisted_fields() -> None:
    event = build_stage_event("retrieve", 2)
    assert event == {"type": "stage", "stage_id": "retrieve", "label_es": "Buscando evidencia en fuentes confiables", "index": 2}
    with pytest.raises(ValueError):
        build_stage_event("not_a_stage", 0)


def test_sse_frame_serializes_only_the_given_payload() -> None:
    frame = sse_frame({"type": "result", "conversation_id": "abc"})
    assert frame.startswith("data: ")
    assert json.loads(frame.removeprefix("data: ")) == {"type": "result", "conversation_id": "abc"}
    assert HEARTBEAT_FRAME == ": ping\n\n"


@pytest.mark.asyncio
async def test_stage_sequence_is_monotonic_without_repetition() -> None:
    seen: list[dict] = []

    async def listener(event: dict) -> None:
        seen.append(event)

    sequence = StageSequence(listener)
    await sequence.emit("classify_intent")
    await sequence.emit("classify_intent")  # repeated stage is suppressed
    await sequence.emit("retrieve")
    assert [event["index"] for event in seen] == [0, 1]
    assert [event["stage_id"] for event in seen] == ["classify_intent", "retrieve"]


def _parse_frames(raw: str) -> list[dict]:
    events = []
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            events.append(json.loads(chunk.removeprefix("data: ")))
    return events


@pytest.mark.asyncio
async def test_chat_stream_yields_ordered_stages_and_single_terminal_result(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.assistant.schemas import AssistantChatRequest
    from app.assistant.service import AssistantService

    # Minimal auth-free service invocation against a fresh in-memory DB.
    session = session_factory()
    service = AssistantService.__new__(AssistantService)
    from app.assistant.repository import AssistantRepository
    from app.assistant.tools import AssistantTools
    from app.jobs.repository import JobRepository
    from app.knowledge.repository import KnowledgeRepository

    repository = AssistantRepository(session)
    service.repository = repository
    service.job_repo = JobRepository(session)
    service.tools = FakeTools(
        classifier_data={
            "language": "es",
            "answer_language": "es",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": None,
            "confidence": 0.9,
            "needs_retrieval": False,
        }
    )
    service.graph = __import__("app").assistant.graph.AssistantGraph(service.tools)
    service._session = session

    frames: list[str] = []
    async for frame in service.chat_stream(
        user_id=uuid4(),
        payload=AssistantChatRequest(message="How often should I water?"),
    ):
        frames.append(frame)
    events = _parse_frames("".join(frames))

    stages = [event for event in events if event["type"] == "stage"]
    terminals = [event for event in events if event["type"] in {"result", "error"}]
    assert [stage["index"] for stage in stages] == list(range(len(stages)))
    assert all(stage["label_es"] == STAGE_LABELS_ES[stage["stage_id"]] for stage in stages)
    assert len(terminals) == 1
    assert events[-1] is terminals[0]
    assert terminals[0]["type"] == "result"
    serialized = json.dumps(events)
    assert "Render a fallback response" not in serialized
    assert "system prompt" not in serialized.lower()


@pytest.mark.asyncio
async def test_stream_route_disabled_returns_404(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASSISTANT_PROGRESS_STREAMING_ENABLED", "false")
    from app.main import app

    token, _, _ = await _seed_user_with_session(session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/assistant/chat/stream",
            json={"message": "Hola"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404


async def _seed_user_with_session(session_factory):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from app.auth.repository import DatabaseAuthRepository

    async with session_factory() as session:
        repository = DatabaseAuthRepository(session)
        user = await repository.create_user("Ada", "stream@example.com", "password123")
        auth_session = await repository.create_session(
            user.id,
            idle_ttl=timedelta(minutes=30),
            absolute_ttl=timedelta(days=1),
        )
        await session.commit()
        return auth_session.token, user.id, uuid4()
