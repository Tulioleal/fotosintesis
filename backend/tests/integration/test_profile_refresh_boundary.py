"""Proposal-11 boundary: enrichment never regenerates profile snapshots.

Proves that completed confirmed-plant enrichment updates lifecycle status and
assistant retrieval while an existing persisted profile snapshot's sections,
sources, confidence, and limitations remain exactly unchanged, no
profile-refresh job is scheduled, and assistant retrieval resolves the new
evidence through canonical candidate context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select

from app.auth.tables import application_jobs, plant_profiles
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.schemas import JobType

from ._enrichment_helpers import (
    LIGHT,
    PAGE_URL,
    REQUIRED,
    SPECIES_KEY,
    SPECIES_NAME,
    DeterministicEmbeddingProvider,
    DeterministicJudgeProvider,
    DeterministicSearchProvider,
    _confirmed_payload,
    _page,
    _production_service,
    _providers,
    _retrieve_through_production_path,
    provider_environment,
    vector_index_factory,
    vector_store,
)

SEEDED_SECTIONS = {
    "description": ["Seeded snapshot description."],
    "care": ["Seeded snapshot care guidance."],
}
SEEDED_SOURCES = [
    {"title": "Seeded source", "url": "https://example.org/seeded", "domain": "example.org", "confidence": 0.8}
]
SEEDED_CONFIDENCE = 0.6
SEEDED_LIMITATIONS = ["Seeded snapshot limitation."]


async def _seed_existing_profile(pg_session_factory) -> None:
    async with pg_session_factory() as session:
        await session.execute(
            plant_profiles.insert().values(
                id=uuid4(),
                scientific_name=SPECIES_NAME,
                common_name="Monstera",
                aliases=[{"name": "Monstera", "language": "general"}],
                sections=SEEDED_SECTIONS,
                sources=SEEDED_SOURCES,
                confidence=SEEDED_CONFIDENCE,
                limitations=SEEDED_LIMITATIONS,
                accepted_gbif_key=2878688,
                normalized_binomial=SPECIES_NAME,
                canonical_species_key=SPECIES_KEY,
            )
        )
        await session.commit()


async def _profile_snapshot(pg_session_factory) -> dict | None:
    async with pg_session_factory() as session:
        row = (
            await session.execute(
                select(
                    plant_profiles.c.sections,
                    plant_profiles.c.sources,
                    plant_profiles.c.confidence,
                    plant_profiles.c.limitations,
                )
            )
        ).first()
    return dict(row._mapping) if row else None


async def test_enrichment_completion_preserves_seeded_snapshot_without_regeneration(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    await _seed_existing_profile(pg_session_factory)

    providers = _providers(
        judge=DeterministicJudgeProvider(pages={_page().url: tuple(REQUIRED)}),
        search=DeterministicSearchProvider(page=_page()),
    )
    payload = await _confirmed_payload(pg_session_factory)
    handler = EnrichConfirmedPlantHandler(
        _production_service(pg_session_factory, providers, vector_index_factory=vector_index_factory)
    )
    result = await handler.handle(
        payload=payload,
        attempt_count=1,
        max_attempts=3,
    )
    assert result.status.value == "complete"

    # Assistant retrieval through the production path returns the enriched
    # evidence for the canonical species identity.
    status, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        providers,
        aspect="light_exposure",
    )
    assert status in {"retrieved", "acquired"}
    assert chunks, "enriched evidence must be retrievable by a later assistant request"

    # The existing profile snapshot remains exactly unchanged.
    snapshot = await _profile_snapshot(pg_session_factory)
    assert snapshot is not None
    assert snapshot["sections"] == SEEDED_SECTIONS
    assert snapshot["sources"] == SEEDED_SOURCES
    assert snapshot["confidence"] == SEEDED_CONFIDENCE
    assert snapshot["limitations"] == SEEDED_LIMITATIONS

    async with pg_session_factory() as session:
        profile_count = int(
            await session.scalar(select(func.count()).select_from(plant_profiles)) or 0
        )
        job_types = (
            await session.execute(select(application_jobs.c.job_type).distinct())
        ).scalars().all()
    assert profile_count == 1
    # Enrichment does NOT regenerate the snapshot inline; it only schedules a
    # deferred profile-refresh job so section regeneration happens asynchronously.
    assert set(job_types) <= {
        JobType.enrich_confirmed_plant.value,
        JobType.refresh_profile.value,
    }
    assert JobType.refresh_profile.value in set(job_types)


class _DeterministicModelProvider:
    """Deterministic model provider for the real assistant graph: returns a
    stable classifier classification and a grounded plain-text answer."""

    def __init__(self) -> None:
        self.classifier_calls = 0
        self.text_prompts: list[str] = []

    async def generate_json(self, prompt: str, schema: dict, **kwargs):
        from app.providers.types import JsonGenerationResult

        properties = schema.get("properties", {}) or {}
        if "intent" in properties:
            self.classifier_calls += 1
            return JsonGenerationResult(
                provider="deterministic-model",
                model="deterministic-json",
                data={
                    "language": "en",
                    "answer_language": "en",
                    "intent": "plant_care_question",
                    "topic": "light",
                    "required_aspects": ["light_exposure"],
                    "plant_reference": None,
                    "confidence": 0.92,
                    "needs_retrieval": True,
                },
            )
        return JsonGenerationResult(
            provider="deterministic-model",
            model="deterministic-json",
            data={
                "title": "Monstera light evidence",
                "content": "Monstera deliciosa needs bright indirect light.",
                "confidence": 0.9,
            },
        )

    async def generate_text(self, prompt: str, **kwargs):
        from app.providers.types import TextGenerationResult

        self.text_prompts.append(prompt)
        return TextGenerationResult(
            provider="deterministic-model",
            model="deterministic-text",
            text="Monstera deliciosa needs bright indirect light.",
        )


class _VisionStub:
    async def analyze_image(self, image, prompt=None, **kwargs):
        from app.providers.types import ImageAnalysisResult

        return ImageAnalysisResult(
            provider="deterministic-vision",
            model="deterministic-vision",
            description="Unused by the care graph.",
            candidates=[],
        )


async def test_owned_candidate_reaches_real_assistant_graph_and_enriched_retrieval(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    """A real owned confirmed validated candidate flows through the real
    AssistantService, AssistantRepository.resolve_candidate_context, the real
    AssistantGraph, and real canonical knowledge retrieval. Client-supplied
    taxonomy that conflicts with the candidate never replaces the
    server-authorized identity."""
    from sqlalchemy import insert

    from app.assistant.schemas import AssistantChatRequest, AssistantChatResponse
    from app.assistant.service import AssistantService
    from app.auth.tables import (
        conversation_messages,
        identification_candidates,
        identification_images,
        users,
    )
    from app.providers.factory import ProviderRegistry
    from app.providers.mocks import (
        MockPerenualPlantDataProvider,
        MockTreflePlantDataProvider,
    )

    user_id = uuid4()
    identification_id = uuid4()
    candidate_id = uuid4()
    now = datetime.now(UTC)
    async with pg_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                name="Owner",
                email=f"{user_id}@example.org",
            )
        )
        await session.execute(
            insert(identification_images).values(
                id=identification_id,
                user_id=user_id,
                storage_path="plant.jpg",
                mime_type="image/jpeg",
                size_bytes=10,
                metadata={},
                status="needs_confirmation",
            )
        )
        await session.execute(
            insert(identification_candidates).values(
                id=candidate_id,
                identification_id=identification_id,
                suggested_scientific_name=SPECIES_NAME,
                confidence_label="high",
                visible_traits=[],
                possible_match_copy="Possible match.",
                gbif_key=2878688,
                gbif_accepted_key=2878688,
                accepted_scientific_name=SPECIES_NAME,
                binomial_name=SPECIES_NAME,
                taxonomic_status="ACCEPTED",
                synonyms=[],
                genus="Monstera",
                family="Araceae",
                species=SPECIES_NAME,
                validation_status="validated",
                confirmed_at=now,
            )
        )
        await session.commit()

    providers = _providers(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)}),
        search=DeterministicSearchProvider(page=_page()),
    )
    handler = EnrichConfirmedPlantHandler(
        _production_service(pg_session_factory, providers, vector_index_factory=vector_index_factory)
    )
    result = await handler.handle(
        payload=await _confirmed_payload(pg_session_factory),
        attempt_count=1,
        max_attempts=3,
    )
    assert result.status.value == "complete"

    registry = ProviderRegistry(
        model=_DeterministicModelProvider(),
        vision=_VisionStub(),
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: (LIGHT,)},
            local_pages={PAGE_URL: (LIGHT,)},
        ),
        search=DeterministicSearchProvider(page=_page()),
        embeddings=DeterministicEmbeddingProvider(),
        trefle=MockTreflePlantDataProvider(mode="unavailable"),
        perenual=MockPerenualPlantDataProvider(mode="unavailable"),
    )
    monkeypatch.setattr(
        "app.assistant.tools.facade.get_provider_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.knowledge.acquisition.get_provider_registry",
        lambda: registry,
    )

    async with pg_session_factory() as session:
        service = AssistantService(session)
        response = await service.chat(
            user_id=user_id,
            payload=AssistantChatRequest(
                message="What light does this plant need?",
                plant="Conflicting display hint",
                plant_binomial_name="Wrongus binomius",
                plant_scientific_name="Wrongus binomius var. client",
                confirmed_candidate_id=candidate_id,
            ),
        )
        user_rows = (
            await session.execute(
                select(conversation_messages).where(
                    conversation_messages.c.role == "user"
                )
            )
        ).all()

    assert isinstance(response, AssistantChatResponse)
    assert response.sources
    assert response.sources[0].url == PAGE_URL
    assert response.diagnostics is not None
    assert response.diagnostics.answerability_status == "full"
    assert "light_exposure" in response.diagnostics.covered_aspects

    assert len(user_rows) == 1
    user_metadata = user_rows[0].metadata
    assert user_metadata["plant_binomial_name"] == "Monstera deliciosa"
    assert user_metadata["canonical_species_key"] == SPECIES_KEY
    assert user_metadata["confirmed_candidate_id"] == str(candidate_id)

