import sys
import types
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.tables import metadata  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.db.session import get_async_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def override_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    async def get_test_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_async_session] = get_test_session
    yield
    app.dependency_overrides.pop(get_async_session, None)


@pytest.fixture(autouse=True)
def reset_provider_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for chain_var in (
        "MODEL_PROVIDERS",
        "JUDGE_PROVIDERS",
        "SEARCH_PROVIDERS",
        "VISION_PROVIDERS",
    ):
        monkeypatch.setenv(chain_var, "[]")
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("JUDGE_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("TREFLE_PROVIDER", "mock")
    monkeypatch.setenv("PERENUAL_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("TREFLE_API_KEY", "")
    monkeypatch.setenv("PERENUAL_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_openai_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponses:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                output_text='{"score": 1, "passed": true, "reasons": []}'
            )

    class FakeEmbeddings:
        async def create(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])],
                usage=types.SimpleNamespace(prompt_tokens=3, total_tokens=3),
            )

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.responses = FakeResponses()
            self.embeddings = FakeEmbeddings()

    openai_module = types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)
    monkeypatch.setitem(sys.modules, "openai", openai_module)


@pytest.fixture
def fake_gemini_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeGenerateContentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakePart:
        @staticmethod
        def from_bytes(*, data: bytes, mime_type: str) -> dict[str, object]:
            return {"data": data, "mime_type": mime_type}

    class FakeGoogleSearch:
        pass

    class FakeTool:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeModels:
        async def generate_content(self, **kwargs: object) -> object:
            return types.SimpleNamespace(
                text='{"score": 1, "passed": true, "reasons": []}'
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            self.api_key = api_key
            self.aio = types.SimpleNamespace(models=FakeModels())

    genai_types_module = types.SimpleNamespace()
    genai_types_module.GenerateContentConfig = FakeGenerateContentConfig
    genai_types_module.Part = FakePart
    genai_types_module.GoogleSearch = FakeGoogleSearch
    genai_types_module.Tool = FakeTool
    genai_module = types.SimpleNamespace(types=genai_types_module, Client=FakeClient)
    google_module = types.SimpleNamespace(genai=genai_module)
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", genai_types_module)
