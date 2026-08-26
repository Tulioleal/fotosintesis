"""PostgreSQL/pgvector convergence tests for enrichment aspect metadata.

Proves that unchanged enrichment content that gains a newly accepted
canonical aspect converges in both the relational aspect-support table and
the pgvector node metadata, using the real production persistence and
retrieval paths with deterministic provider-boundary fakes.
"""

import asyncio
from datetime import UTC, datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.auth.tables import (
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
    taxonomy_provenance_snapshots,
)
from app.core.settings import get_settings
from app.enrichment.evidence import AcceptedEnrichmentClaim, EnrichmentEvidencePersistenceService
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import ENRICHMENT_POLICY_V1
from app.enrichment.progress import EnrichmentProgressRepository
from app.knowledge.rag import KnowledgeVectorIndex, LlamaIndexRuntime, VectorIndexError
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import KnowledgeRetrievalFilters

from ._enrichment_helpers import (
    _all_vector_node_ids,
    fake_embedding_dimension,
)
from app.providers.types import EmbeddingResult

from .conftest import BASE_DATABASE_URL

WATERING = "watering_frequency_or_trigger"
LIGHT = "light_exposure"


@pytest.mark.asyncio
async def test_concurrent_progress_updates_preserve_accepted_aspect_union(
    pg_session_factory,
    enrichment_job_id,
) -> None:
    required = sorted(
        aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects
    )
    async with pg_session_factory() as session:
        progress = EnrichmentProgressRepository(session)
        await progress.initialize_or_load(
            job_id=enrichment_job_id,
            policy_version=ENRICHMENT_POLICY_V1.version,
            required_aspects=required,
        )
        await session.commit()

    async def record(aspect: str) -> None:
        async with pg_session_factory() as session:
            progress = EnrichmentProgressRepository(session)
            await progress.record_persisted_aspects(
                job_id=enrichment_job_id,
                persisted_aspects=[aspect],
            )
            await asyncio.sleep(0.05)
            await session.commit()

    await asyncio.gather(record(LIGHT), record(WATERING))

    async with pg_session_factory() as session:
        snapshot = await EnrichmentProgressRepository(
            session
        ).get_for_terminalization(job_id=enrichment_job_id)

    assert snapshot is not None
    assert set(snapshot.persisted_covered_aspects) == {LIGHT, WATERING}
    assert snapshot.accepted_aspect_count == 2


class _EmbeddingProvider:
    async def create_embeddings(self, texts: list[str], **kwargs) -> EmbeddingResult:
        dimension = fake_embedding_dimension()

        return EmbeddingResult(
            provider="convergence",
            model=f"convergence-{dimension}d",
            embeddings=[[0.1] * dimension for _ in texts],
        )


def _identity() -> CanonicalSpeciesIdentity:
    return CanonicalSpeciesIdentity(
        accepted_gbif_key=2878688,
        normalized_binomial="Monstera deliciosa",
        taxonomy_validated=True,
    )


@pytest.fixture
async def taxonomy_provenance_id(pg_session_factory) -> uuid4:
    from sqlalchemy import insert

    provenance_id = uuid4()
    identity = _identity()
    async with pg_session_factory() as session:
        await session.execute(
            insert(taxonomy_provenance_snapshots).values(
                id=provenance_id,
                canonical_species_key=identity.key,
                accepted_gbif_key=identity.accepted_gbif_key,
                normalized_binomial=identity.normalized_binomial,
                taxonomy_source="gbif",
                taxonomy_source_version="fixture",
                snapshot={"accepted": True},
                resolved_at=datetime(2026, 8, 1, tzinfo=UTC),
            )
        )
        await session.commit()
    return provenance_id


@pytest.fixture
async def enrichment_job_id(pg_session_factory) -> uuid4:
    from sqlalchemy import insert

    from app.auth.tables import application_jobs

    job_id = uuid4()
    now = datetime(2026, 8, 1, tzinfo=UTC)
    async with pg_session_factory() as session:
        await session.execute(
            insert(application_jobs).values(
                id=job_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={"run_id": str(job_id)},
                status="processing",
                idempotency_key=f"convergence-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return job_id


def _claim(*, aspects: tuple[str, ...]) -> AcceptedEnrichmentClaim:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    return AcceptedEnrichmentClaim(
        claim="Use bright indirect light and water when the substrate dries.",
        evidence_quote=(
            "Provide bright indirect light and allow the substrate to dry before watering."
        ),
        source_url="https://example.org/monstera-care",
        source_title="Monstera care",
        source_domain="example.org",
        source_version="etag-v1",
        source_retrieved_at=now,
        source_published_at=None,
        supported_aspects=aspects,
        confidence=0.95,
    )


@pytest.fixture
async def vector_store(pg_schema):
    from llama_index.vector_stores.postgres import PGVectorStore

    url = make_url(BASE_DATABASE_URL)
    store = PGVectorStore.from_params(
        database=url.database,
        host=url.host,
        password=url.password,
        port=url.port,
        user=url.username,
        table_name="enrichment_aspect_convergence",
        schema_name=pg_schema,
        embed_dim=fake_embedding_dimension(),
        use_jsonb=True,
    )
    try:
        yield store
    finally:
        await store.close()


@pytest.fixture
def vector_index_factory(vector_store):
    runtime = LlamaIndexRuntime(
        get_settings(), vector_store_factory=lambda: vector_store
    )
    return lambda repository: KnowledgeVectorIndex(repository, runtime=runtime)


def _service(session_factory, vector_index_factory):
    session = session_factory()
    repository = KnowledgeRepository(session, get_settings())
    return (
        EnrichmentEvidencePersistenceService(
            repository,
            vector_index=vector_index_factory(repository),
            embedding_provider=_EmbeddingProvider(),
        ),
        session,
    )


async def _record_validation(
    session_factory, *, state, covered, job_id=None, taxonomy_provenance_id=None
) -> UUID:
    service, session = _service(session_factory, lambda repo: None)
    validation_id = await service.record_validation(
        job_id=job_id or uuid4(),
        taxonomy_provenance_id=taxonomy_provenance_id or uuid4(),
        policy_version=1,
        required_aspects=[WATERING, LIGHT],
        covered_aspects=list(covered),
        missing_aspects=[],
        answerability_status="full",
        judge_confidence=0.95,
        validation_metadata={"acquisition_avoided": False},
    )
    await session.close()
    return validation_id


async def _counts(session_factory) -> dict[str, int]:
    async with session_factory() as session:
        counts = {}
        for name, table in (
            ("documents", knowledge_documents),
            ("sources", knowledge_sources),
            ("chunks", knowledge_chunks),
            ("embeddings", knowledge_embeddings),
            ("supports", knowledge_document_aspect_supports),
        ):
            counts[name] = int(
                await session.scalar(select(func.count()).select_from(table)) or 0
            )
        return counts


async def _aspect_support_set(session_factory) -> set[str]:
    async with session_factory() as session:
        return set(
            (
                await session.execute(
                    select(knowledge_document_aspect_supports.c.aspect)
                )
            ).scalars().all()
        )


async def _retrieve_chunk(
    vector_index_factory,
    session_factory,
    *,
    aspect: str,
) -> list:
    async with session_factory() as session:
        index = vector_index_factory(KnowledgeRepository(session, get_settings()))
        return await index.retrieve_chunks(
            KnowledgeRetrievalFilters(
                canonical_species_key=_identity().key,
                evidence_type="confirmed_plant_enrichment",
                covered_aspect=aspect,
            ),
            query_text=f"Monstera deliciosa {aspect}",
            query_embedding=[0.1] * fake_embedding_dimension(),
            limit=5,
        )


async def _assert_vector_equals_relational(vector_store, session_factory) -> None:
    async with session_factory() as session:
        chunk_ids = list(
            (await session.execute(select(knowledge_chunks.c.id))).scalars().all()
        )
    relational_ids = {str(chunk_id) for chunk_id in chunk_ids}
    vector_ids = await _all_vector_node_ids(vector_store)
    assert vector_ids == relational_ids


async def test_existing_content_gaining_an_aspect_becomes_retrievable_by_that_aspect(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    first_service, first_session = _service(pg_session_factory, vector_index_factory)
    try:
        first = await first_service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT,)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=first,
            covered={LIGHT},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await first_service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=first.document_id,
            )

        second_service, second_session = _service(
            pg_session_factory, vector_index_factory
        )
        try:
            second = await second_service.persist_claim_relational(
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                claim=_claim(aspects=(LIGHT, WATERING)),
            )
        finally:
            await second_session.close()
        validation_id = await _record_validation(
            pg_session_factory,
            state=second,
            covered={LIGHT, WATERING},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await first_service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=second.document_id,
            )
    finally:
        await first_session.close()

    assert second.document_id == first.document_id
    assert sorted(
        chunk.metadata.get("covered_aspects") for chunk in second.chunks
    ) == [[LIGHT, WATERING]]
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 2,
    }

    nodes = await vector_store.aget_nodes(node_ids=[str(first.chunks[0].id)])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == [LIGHT, WATERING]

    watering = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=WATERING
    )
    light = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=LIGHT
    )
    assert len(watering) == 1
    assert len(light) == 1
    assert watering[0].id == first.chunks[0].id
    assert light[0].id == first.chunks[0].id


async def test_retry_after_relational_commit_and_vector_failure_converges_without_duplicates(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    from app.auth.tables import enrichment_validation_evidence

    service, session = _service(pg_session_factory, vector_index_factory)
    try:
        first = await service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT,)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=first,
            covered={LIGHT},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=first.document_id,
            )

        second = await service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT, WATERING)),
        )
        assert second.document_id == first.document_id
        assert sorted(
            chunk.metadata.get("covered_aspects") for chunk in second.chunks
        ) == [[LIGHT, WATERING]]
        validation_id = await _record_validation(
            pg_session_factory,
            state=second,
            covered={LIGHT, WATERING},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
    finally:
        await session.close()

    # Inject the vector failure through the real persistence service so the
    # failure happens inside Phase B after the relational commit of Phase A.
    failing_service, failing_session = _service(
        pg_session_factory, vector_index_factory
    )
    index = failing_service.vector_index

    async def fail_vector_nodes(**kwargs) -> None:
        raise VectorIndexError("transient pgvector metadata refresh failure")

    index.ensure_vector_nodes = fail_vector_nodes  # type: ignore[method-assign]
    with pytest.raises(VectorIndexError):
        await failing_service.associate_validation_and_refresh(
            validation_id=validation_id,
            document_id=second.document_id,
        )
    await failing_session.close()

    # Phase A relational support survives the vector failure; the Phase B
    # association rolled back and no new vector node exists.
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 2,
    }
    async with pg_session_factory() as session:
        association_count = int(
            await session.scalar(
                select(func.count())
                .select_from(enrichment_validation_evidence)
                .where(
                    enrichment_validation_evidence.c.validation_run_id
                    == validation_id
                )
            )
            or 0
        )
    assert association_count == 0
    nodes = await vector_store.aget_nodes(node_ids=[str(first.chunks[0].id)])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == [LIGHT]

    retry_service, retry_session = _service(pg_session_factory, vector_index_factory)
    try:
        retried = await retry_service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT, WATERING)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=retried,
            covered={LIGHT, WATERING},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await retry_service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=retried.document_id,
            )
    finally:
        await retry_session.close()

    assert retried.document_id == first.document_id
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 2,
    }
    nodes = await vector_store.aget_nodes(node_ids=[str(first.chunks[0].id)])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == [LIGHT, WATERING]

    async with pg_session_factory() as session:
        association_count = int(
            await session.scalar(
                select(func.count())
                .select_from(enrichment_validation_evidence)
                .where(
                    enrichment_validation_evidence.c.validation_run_id
                    == validation_id
                )
            )
            or 0
        )
    assert association_count == 1

    by_aspect = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=WATERING
    )
    assert len(by_aspect) == 1
    assert by_aspect[0].id == first.chunks[0].id
    await _assert_vector_equals_relational(vector_store, pg_session_factory)


class _FailAfterPersistedCheckpoint(EnrichmentProgressRepository):
    """Progress repository that performs the real checkpoint update and then
    fails, proving the update is rolled back with the rest of Phase A."""

    async def record_persisted_aspects(
        self,
        *,
        job_id,
        persisted_aspects,
    ):
        await super().record_persisted_aspects(
            job_id=job_id,
            persisted_aspects=persisted_aspects,
        )
        raise RuntimeError("fail after real checkpoint update")


async def test_checkpoint_failure_after_real_update_rolls_back_phase_a(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    required = sorted(
        aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects
    )
    async with pg_session_factory() as session:
        progress = EnrichmentProgressRepository(session)
        await progress.initialize_or_load(
            job_id=enrichment_job_id,
            policy_version=ENRICHMENT_POLICY_V1.version,
            required_aspects=required,
        )
        await session.commit()

    session = pg_session_factory()
    repository = KnowledgeRepository(session, get_settings())
    failing_progress = _FailAfterPersistedCheckpoint(session)
    service = EnrichmentEvidencePersistenceService(
        repository,
        vector_index=vector_index_factory(repository),
        embedding_provider=_EmbeddingProvider(),
    )
    try:
        with pytest.raises(RuntimeError, match="fail after real checkpoint update"):
            await service.persist_claim_relational(
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                claim=_claim(aspects=(LIGHT,)),
                job_id=enrichment_job_id,
                progress=failing_progress,
            )
    finally:
        await session.close()

    assert await _counts(pg_session_factory) == {
        "documents": 0,
        "sources": 0,
        "chunks": 0,
        "embeddings": 0,
        "supports": 0,
    }

    async with pg_session_factory() as session:
        snapshot = await EnrichmentProgressRepository(
            session
        ).get_for_terminalization(job_id=enrichment_job_id)
    assert snapshot is not None
    assert snapshot.persisted_covered_aspects == ()
    assert snapshot.indexed_covered_aspects == ()
    assert snapshot.accepted_aspect_count == 0


async def test_replayed_validation_association_produces_one_row(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    from app.auth.tables import enrichment_validation_evidence

    service, session = _service(pg_session_factory, vector_index_factory)
    try:
        state = await service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT,)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=state,
            covered={LIGHT},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
        await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
    finally:
        await session.close()

    async with pg_session_factory() as session:
        association_count = int(
            await session.scalar(
                select(func.count())
                .select_from(enrichment_validation_evidence)
                .where(
                    enrichment_validation_evidence.c.validation_run_id
                    == validation_id
                )
            )
            or 0
        )
    assert association_count == 1
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 1,
    }
    nodes = await vector_store.aget_nodes(node_ids=[str(state.chunks[0].id)])
    assert len(nodes) == 1


async def test_stale_chunk_json_covered_aspects_are_ignored(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    from sqlalchemy import update

    from app.auth.tables import enrichment_validation_evidence

    service, session = _service(pg_session_factory, vector_index_factory)
    try:
        state = await service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT,)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=state,
            covered={LIGHT},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
    finally:
        await session.close()

    # Deliberately corrupt the persisted chunk JSON so only a reload from the
    # relational aspect-support table can produce the correct metadata.
    async with pg_session_factory() as session:
        await session.execute(
            update(knowledge_chunks)
            .values(
                metadata={
                    **state.chunks[0].metadata,
                    "covered_aspects": ["made_up_stale_aspect"],
                }
            )
        )
        await session.commit()

    service, session = _service(pg_session_factory, vector_index_factory)
    try:
        gained = await service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT, WATERING)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=gained,
            covered={LIGHT, WATERING},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=gained.document_id,
            )
    finally:
        await session.close()

    async with pg_session_factory() as session:
        stored_metadata = (
            await session.execute(select(knowledge_chunks.c.metadata))
        ).scalars().all()
    assert all(
        sorted(metadata.get("covered_aspects") or []) == [LIGHT, WATERING]
        for metadata in stored_metadata
    )
    nodes = await vector_store.aget_nodes(node_ids=[str(gained.chunks[0].id)])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == [LIGHT, WATERING]
    assert "made_up_stale_aspect" not in nodes[0].metadata["covered_aspects"]


class _GatedVectorIndex:
    """Delegates to the real index but pauses the first vector upsert until
    ``release`` is set, forcing concurrent Phase B operations to interleave."""

    def __init__(self, real, entered: asyncio.Event, release: asyncio.Event) -> None:
        self._real = real
        self._entered = entered
        self._release = release
        self.calls = 0

    def __getattr__(self, name: str):
        return getattr(self._real, name)

    async def ensure_vector_nodes(self, **kwargs) -> None:
        self.calls += 1
        if self.calls == 1:
            self._entered.set()
            await self._release.wait()
        await self._real.ensure_vector_nodes(**kwargs)


async def test_concurrent_phase_b_operations_forced_to_interleave_converge_to_union(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    from app.auth.tables import enrichment_validation_evidence

    service_a, session_a = _service(pg_session_factory, vector_index_factory)
    service_b, session_b = _service(pg_session_factory, vector_index_factory)
    entered = asyncio.Event()
    release = asyncio.Event()
    gated = _GatedVectorIndex(service_a.vector_index, entered, release)
    service_a.vector_index = gated
    service_b.vector_index = gated

    try:
        state_a = await service_a.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT,)),
        )
        validation_id_a = await _record_validation(
            pg_session_factory,
            state=state_a,
            covered={LIGHT},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        state_b = await service_b.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(WATERING,)),
        )
        validation_id_b = await _record_validation(
            pg_session_factory,
            state=state_b,
            covered={WATERING},
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        assert state_a.document_id == state_b.document_id

        async def refresh(service, session, state, validation_id) -> None:
            try:
                await service.associate_validation_and_refresh(
                    validation_id=validation_id,
                    document_id=state.document_id,
                )
            finally:
                await session.close()

        task_a = asyncio.create_task(
            refresh(service_a, session_a, state_a, validation_id_a)
        )
        await entered.wait()
        task_b = asyncio.create_task(
            refresh(service_b, session_b, state_b, validation_id_b)
        )
        await asyncio.sleep(0.2)
        assert gated.calls == 1, "second refresh must block on the document lock"
        release.set()
        await asyncio.gather(task_a, task_b)
    finally:
        release.set()
        await session_a.close()
        await session_b.close()

    assert await _aspect_support_set(pg_session_factory) == {LIGHT, WATERING}
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 2,
    }
    async with pg_session_factory() as session:
        association_count = int(
            await session.scalar(
                select(func.count()).select_from(enrichment_validation_evidence)
            )
            or 0
        )
    assert association_count == 2
    nodes = await vector_store.aget_nodes(node_ids=[str(state_a.chunks[0].id)])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == [LIGHT, WATERING]

    watering = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=WATERING
    )
    light = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=LIGHT
    )
    assert len(watering) == 1
    assert len(light) == 1
    assert watering[0].id == state_a.chunks[0].id
    assert light[0].id == state_a.chunks[0].id
    await _assert_vector_equals_relational(vector_store, pg_session_factory)


async def test_concurrent_validations_add_different_aspects_and_converge_to_union(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    """Two concurrent complete operations (persist -> validate -> index) must
    converge naturally under the document row lock, without a later repair
    call."""

    async def run_operation(aspects: tuple[str, ...]):
        service, session = _service(pg_session_factory, vector_index_factory)
        try:
            state = await service.persist_claim_relational(
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                claim=_claim(aspects=aspects),
            )
            validation_id = await _record_validation(
                pg_session_factory,
                state=state,
                covered=set(aspects),
                job_id=enrichment_job_id,
                taxonomy_provenance_id=taxonomy_provenance_id,
            )
            await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
            return state
        finally:
            await session.close()

    state_light, state_watering = await asyncio.gather(
        run_operation((LIGHT,)),
        run_operation((WATERING,)),
    )

    assert state_light.document_id == state_watering.document_id

    assert await _aspect_support_set(pg_session_factory) == {LIGHT, WATERING}
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 2,
    }

    async with pg_session_factory() as session:
        stored_metadata = (
            await session.execute(select(knowledge_chunks.c.metadata))
        ).scalars().all()
    assert all(
        sorted(metadata.get("covered_aspects") or []) == [LIGHT, WATERING]
        for metadata in stored_metadata
    )

    nodes = await vector_store.aget_nodes(node_ids=[str(state_light.chunks[0].id)])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == [LIGHT, WATERING]

    watering = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=WATERING
    )
    light = await _retrieve_chunk(
        vector_index_factory, pg_session_factory, aspect=LIGHT
    )
    assert len(watering) == 1
    assert len(light) == 1
    assert watering[0].id == state_light.chunks[0].id
    assert light[0].id == state_light.chunks[0].id
    await _assert_vector_equals_relational(vector_store, pg_session_factory)


async def test_production_like_dataset_relational_and_vector_metadata_agree(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    """Compare relational aspect associations with vector-node metadata over a
    production-like dataset with varying aspect sets and content versions."""
    datasets = [
        ((WATERING,), "etag-v1", "Use bright indirect light."),
        ((WATERING, LIGHT), "etag-v1", "Use bright indirect light."),
        ((WATERING, LIGHT), "etag-v2", "Use bright indirect light."),
        ((WATERING,), "etag-v3", "Keep the soil evenly moist."),
        ((WATERING, LIGHT), "etag-v3", "Keep the soil evenly moist."),
        ((WATERING, LIGHT, "humidity_preference"), "etag-v3", "Keep the soil evenly moist."),
    ]
    service, session = _service(pg_session_factory, vector_index_factory)
    try:
        from dataclasses import replace

        for index, (aspects, version, claim_text) in enumerate(datasets):
            claim = replace(
                _claim(aspects=aspects),
                source_version=version,
                claim=claim_text,
                evidence_quote=f"Paraphrased evidence quote for {claim_text}.",
            )
            state = await service.persist_claim_relational(
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                claim=claim,
            )
            validation_id = await _record_validation(
                pg_session_factory,
                state=state,
                covered=set(aspects),
                job_id=enrichment_job_id,
                taxonomy_provenance_id=taxonomy_provenance_id,
            )
            await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
    finally:
        await session.close()

    async with pg_session_factory() as session:
        rows = (
            await session.execute(
                select(
                    knowledge_documents.c.id,
                    knowledge_documents.c.canonical_source_url,
                    knowledge_documents.c.source_version,
                    knowledge_documents.c.normalized_content_hash,
                )
            )
        ).all()
        assert len(rows) == 3
        content_keys = {
            (str(row[1]), str(row[2]), str(row[3])) for row in rows
        }
        assert len(content_keys) == len(rows)

        supports = (
            await session.execute(
                select(
                    knowledge_document_aspect_supports.c.document_id,
                    knowledge_document_aspect_supports.c.aspect,
                )
            )
        ).all()
        relational_by_doc: dict[str, set[str]] = {}
        for document_id, aspect in supports:
            relational_by_doc.setdefault(str(document_id), set()).add(aspect)

        chunks = (
            await session.execute(
                select(
                    knowledge_chunks.c.id,
                    knowledge_chunks.c.document_id,
                )
            )
        ).all()

    nodes = await vector_store.aget_nodes(node_ids=[str(row[0]) for row in chunks])
    relational_ids = {str(row[0]) for row in chunks}
    vector_ids = await _all_vector_node_ids(vector_store)
    assert vector_ids == relational_ids
    vector_by_doc: dict[str, set[str]] = {}
    for node in nodes:
        chunk_row = next(
            row for row in chunks if str(row[0]) == node.node_id
        )
        vector_by_doc.setdefault(str(chunk_row[1]), set()).update(
            node.metadata.get("covered_aspects") or []
        )

    assert set(relational_by_doc) == set(vector_by_doc)
    for document_id, relational_aspects in relational_by_doc.items():
        assert relational_aspects == vector_by_doc[document_id], document_id
    assert sorted(
        frozenset(aspects) for aspects in relational_by_doc.values()
    ) == [
        frozenset({WATERING, LIGHT}),
        frozenset({WATERING, LIGHT}),
        frozenset({WATERING, LIGHT, "humidity_preference"}),
    ]


class _AspectRankEmbeddingProvider:
    """Requested marker content is embedded far from the query; unrelated
    marker content is embedded near it, so similarity rank opposes aspect."""

    async def create_embeddings(self, texts: list[str], **kwargs) -> EmbeddingResult:
        embeddings = []
        for text in texts:
            if "REQUESTED_MARKER" in text:
                embeddings.append([0.0] * fake_embedding_dimension())
            else:
                embeddings.append([0.1] * fake_embedding_dimension())
        return EmbeddingResult(
            provider="convergence",
            model=f"convergence-{fake_embedding_dimension()}d",
            embeddings=embeddings,
        )


async def test_aspect_filtered_retrieval_survives_higher_scoring_unrelated_chunks(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    from dataclasses import replace

    from app.knowledge.acquisition import KnowledgeAcquisitionService, TrustedSourceValidator
    from app.providers.types import SearchResult

    async def persist(claim_text: str, quote: str, aspects: tuple[str, ...], embedding_provider):
        async with pg_session_factory() as session:
            repository = KnowledgeRepository(session, get_settings())
            service = EnrichmentEvidencePersistenceService(
                repository,
                vector_index=vector_index_factory(repository),
                embedding_provider=embedding_provider,
            )
            claim = replace(
                _claim(aspects=aspects),
                claim=claim_text,
                evidence_quote=quote,
                source_version="aspect-rank",
            )
            state = await service.persist_claim_relational(
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                claim=claim,
            )
            validation_id = await _record_validation(
                pg_session_factory,
                state=state,
                covered=set(aspects),
                job_id=enrichment_job_id,
                taxonomy_provenance_id=taxonomy_provenance_id,
            )
            await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
            return state

    requested = await persist(
        "REQUESTED_MARKER bright indirect light.",
        "REQUESTED_MARKER paraphrase quote.",
        (WATERING,),
        _AspectRankEmbeddingProvider(),
    )
    unrelated_aspects = ("soil_drainage", "humidity_preference", "climate_temperature_range")
    for index in range(24):
        await persist(
            f"UNRELATED_MARKER aspect {index % len(unrelated_aspects)} content.",
            f"UNRELATED_MARKER quote {index}.",
            (unrelated_aspects[index % len(unrelated_aspects)],),
            _AspectRankEmbeddingProvider(),
        )

    async with pg_session_factory() as session:
        repository = KnowledgeRepository(session, get_settings())
        service = KnowledgeAcquisitionService(
            repository,
            providers=SimpleNamespace(
                model=object(),
                search=object(),
                embeddings=_AspectRankEmbeddingProvider(),
            ),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=vector_index_factory(repository),
        )
        result = await service.retrieve_or_acquire(
            scientific_name="Monstera deliciosa",
            topic="confirmed_plant_enrichment",
            canonical_species_key=_identity().key,
            accepted_gbif_key=2878688,
            required_aspects=[WATERING],
            question=WATERING,
        )

    assert result.status.value == "retrieved"
    assert requested.chunks[0].id in {chunk.id for chunk in result.chunks}


async def test_balanced_ordering_survives_production_local_judge_budget(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    """Coverage-balanced ordering is preserved through the production local
    semantic judge budget: with a budget of MAX_JUDGE_SOURCES and unrelated
    higher-scoring chunks present, each requested aspect still contributes a
    candidate before any aspect contributes a duplicate."""
    from dataclasses import replace

    from app.enrichment.service import MAX_JUDGE_SOURCES
    from app.knowledge.acquisition import retrieve_balanced_enrichment

    async def persist(claim_text: str, quote: str, aspects: tuple[str, ...], embedding_provider):
        async with pg_session_factory() as session:
            repository = KnowledgeRepository(session, get_settings())
            service = EnrichmentEvidencePersistenceService(
                repository,
                vector_index=vector_index_factory(repository),
                embedding_provider=embedding_provider,
            )
            claim = replace(
                _claim(aspects=aspects),
                claim=claim_text,
                evidence_quote=quote,
                source_version="balance-budget",
            )
            state = await service.persist_claim_relational(
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                claim=claim,
            )
            validation_id = await _record_validation(
                pg_session_factory,
                state=state,
                covered=set(aspects),
                job_id=enrichment_job_id,
                taxonomy_provenance_id=taxonomy_provenance_id,
            )
            await service.associate_validation_and_refresh(
                validation_id=validation_id,
                document_id=state.document_id,
            )
            return state

    # Two requested aspects carry marker content embedded far from the query,
    # while unrelated higher-scoring chunks fill the pgvector top-k.
    watering = await persist(
        "REQUESTED_MARKER watering guidance.",
        "REQUESTED_MARKER watering quote.",
        (WATERING,),
        _AspectRankEmbeddingProvider(),
    )
    light = await persist(
        "REQUESTED_MARKER light guidance.",
        "REQUESTED_MARKER light quote.",
        (LIGHT,),
        _AspectRankEmbeddingProvider(),
    )
    unrelated_aspects = ("soil_drainage", "humidity_preference", "climate_temperature_range")
    for index in range(24):
        await persist(
            f"UNRELATED_MARKER aspect {index % len(unrelated_aspects)} content.",
            f"UNRELATED_MARKER quote {index}.",
            (unrelated_aspects[index % len(unrelated_aspects)],),
            _AspectRankEmbeddingProvider(),
        )

    async with pg_session_factory() as session:
        repository = KnowledgeRepository(session, get_settings())
        result = await retrieve_balanced_enrichment(
            vector_index=vector_index_factory(repository),
            canonical_species_key=_identity().key,
            accepted_gbif_key=2878688,
            required_aspects=[WATERING, LIGHT],
            query_text="care",
            query_embedding=[0.0] * fake_embedding_dimension(),
            per_aspect_limit=5,
            budget=MAX_JUDGE_SOURCES,
        )

    ids = [str(chunk.id) for chunk in result]
    watering_id = str(watering.chunks[0].id)
    light_id = str(light.chunks[0].id)
    unrelated_ids = [chunk_id for chunk_id in ids if chunk_id not in {watering_id, light_id}]
    assert len(result) <= MAX_JUDGE_SOURCES
    assert watering_id in ids and light_id in ids
    # Both requested aspects lead the balanced ordering before any unrelated
    # higher-scoring chunk, and each requested chunk appears exactly once.
    assert ids.index(watering_id) < ids.index(light_id)
    if unrelated_ids:
        assert ids.index(light_id) < ids.index(unrelated_ids[0])


async def test_new_profile_snapshot_includes_only_accepted_canonical_evidence(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id,
    enrichment_job_id,
) -> None:
    """A new canonical profile snapshot includes only enrichment documents
    whose aspect support and validation provenance cover the same accepted
    aspect, with trusted source provenance and eligible review state. Each
    exclusion gate is arranged independently so a single broken gate cannot
    hide behind another."""
    from sqlalchemy import insert

    from app.auth.tables import (
        enrichment_validation_evidence,
        enrichment_validation_runs,
        knowledge_document_aspect_supports,
        knowledge_sources,
        plant_profiles,
    )
    from app.knowledge.schemas import ReviewStatus
    from app.profile_garden.repository import PlantProfileGardenRepository

    accepted_support = {LIGHT, WATERING}

    # Accepted canonical evidence: aspect support and validation provenance
    # both cover the same aspects, with trusted source and eligible review.
    service, session = _service(pg_session_factory, vector_index_factory)
    try:
        accepted = await service.persist_claim_relational(
            identity=_identity(),
            taxonomy_provenance_id=taxonomy_provenance_id,
            claim=_claim(aspects=(LIGHT, WATERING)),
        )
        validation_id = await _record_validation(
            pg_session_factory,
            state=accepted,
            covered=accepted_support,
            job_id=enrichment_job_id,
            taxonomy_provenance_id=taxonomy_provenance_id,
        )
        await service.associate_validation_and_refresh(
            validation_id=validation_id,
            document_id=accepted.document_id,
        )
    finally:
        await session.close()
    await _annotate_accepted_marker(pg_session_factory, accepted.document_id)

    # Independent negative arrangements, each exercising exactly one gate:
    # mismatched aspect validation, legacy null-key fallback, untrusted
    # source, rejected review state, missing support, missing validation.
    fixtures = [
        (
            "MISMATCHED_ASPECT_MARKER",
            dict(
                supports={WATERING},
                validation_covered={LIGHT},
                canonical=True,
                source_validation="trusted",
                review=ReviewStatus.auto_ingested.value,
            ),
        ),
        (
            "LEGACY_FALLBACK_MARKER",
            dict(
                supports={WATERING},
                validation_covered={WATERING},
                canonical=False,
                source_validation="trusted",
                review=ReviewStatus.auto_ingested.value,
            ),
        ),
        (
            "UNTRUSTED_MARKER",
            dict(
                supports={WATERING},
                validation_covered={WATERING},
                canonical=True,
                source_validation="untrusted",
                review=ReviewStatus.auto_ingested.value,
            ),
        ),
        (
            "REJECTED_REVIEW_MARKER",
            dict(
                supports={WATERING},
                validation_covered={WATERING},
                canonical=True,
                source_validation="trusted",
                review=ReviewStatus.rejected.value,
            ),
        ),
        (
            "NO_SUPPORT_MARKER",
            dict(
                supports=set(),
                validation_covered={WATERING},
                canonical=True,
                source_validation="trusted",
                review=ReviewStatus.auto_ingested.value,
            ),
        ),
        (
            "NO_VALIDATION_MARKER",
            dict(
                supports={WATERING},
                validation_covered=set(),
                canonical=True,
                source_validation="trusted",
                review=ReviewStatus.auto_ingested.value,
            ),
        ),
    ]
    async with pg_session_factory() as session:
        for index, (marker, options) in enumerate(fixtures):
            await _insert_canonical_fixture(
                session,
                marker=marker,
                identity=_identity(),
                taxonomy_provenance_id=taxonomy_provenance_id,
                job_id=enrichment_job_id,
                index=index,
                **options,
            )
        await session.commit()

        profile = await PlantProfileGardenRepository(session).get_or_create_profile(
            scientific_name=_identity().normalized_binomial,
            common_name="Monstera",
            accepted_gbif_key=_identity().accepted_gbif_key,
            normalized_binomial=_identity().normalized_binomial,
            canonical_species_key=_identity().key,
        )

    combined = " ".join(
        item for section in profile.sections.values() for item in section
    )
    assert "ACCEPTED_COUPLED_MARKER" in combined
    assert "MISMATCHED_ASPECT_MARKER" not in combined
    assert "LEGACY_FALLBACK_MARKER" not in combined
    assert "UNTRUSTED_MARKER" not in combined
    assert "REJECTED_REVIEW_MARKER" not in combined
    assert "NO_SUPPORT_MARKER" not in combined
    assert "NO_VALIDATION_MARKER" not in combined
    # The accepted evidence document is referenced as a snapshot source.
    assert profile.sources
    async with pg_session_factory() as session:
        profile_total = await session.scalar(
            select(func.count()).select_from(plant_profiles)
        )
    assert profile_total == 1


async def _annotate_accepted_marker(session_factory, document_id: UUID) -> None:
    """Tag the accepted document's chunk content with the accepted marker."""
    from app.auth.tables import knowledge_chunks

    async with session_factory() as session:
        chunks = (
            await session.execute(
                select(knowledge_chunks).where(
                    knowledge_chunks.c.document_id == document_id
                )
            )
        ).mappings().all()
        assert chunks
        for chunk in chunks:
            await session.execute(
                knowledge_chunks.update()
                .where(knowledge_chunks.c.id == chunk["id"])
                .values(content=chunk["content"] + " ACCEPTED_COUPLED_MARKER")
            )
        await session.commit()


async def _insert_canonical_fixture(
    session,
    *,
    marker: str,
    identity,
    taxonomy_provenance_id: UUID,
    job_id: UUID,
    index: int,
    supports: set[str],
    validation_covered: set[str],
    canonical: bool,
    source_validation: str,
    review: str,
) -> None:
    from sqlalchemy import insert

    from app.auth.tables import (
        enrichment_validation_evidence,
        enrichment_validation_runs,
        knowledge_document_aspect_supports,
        knowledge_sources,
    )
    from app.knowledge.schemas import ReviewStatus

    now = datetime.now(UTC)
    document_id = uuid4()
    chunk_id = uuid4()
    source_id = uuid4()
    key = identity.key if canonical else None
    source_url = f"https://example.org/marker-{index}"
    content = f"{marker} content must never enter the snapshot unless accepted."
    await session.execute(
        insert(knowledge_documents).values(
            id=document_id,
            scientific_name=identity.normalized_binomial,
            topic="confirmed_plant_enrichment",
            title=marker,
            content=content,
            confidence=0.9,
            review_status=review,
            canonical_species_key=key,
            accepted_gbif_key=identity.accepted_gbif_key if canonical else None,
            normalized_binomial=identity.normalized_binomial,
            canonical_source_url=source_url,
            canonical_source_domain="example.org",
            source_version=f"etag-marker-{index}",
            normalized_content_hash=f"{marker}{index}".ljust(64, "0")[:64],
            source_retrieved_at=now,
            enrichment_provenance={"kind": "confirmed_plant_enrichment", "version": 1},
            taxonomy_provenance_id=taxonomy_provenance_id if canonical else None,
        )
    )
    await session.execute(
        insert(knowledge_sources).values(
            id=source_id,
            document_id=document_id,
            title=marker,
            url=source_url,
            source_domain="example.org",
            retrieved_at=now,
            validation_status=source_validation,
        )
    )
    await session.execute(
        insert(knowledge_chunks).values(
            id=chunk_id,
            document_id=document_id,
            source_id=source_id,
            chunk_index=0,
            content=content,
            metadata={},
            scientific_name=identity.normalized_binomial,
            topic="confirmed_plant_enrichment",
            source_domain="example.org",
            source_url=source_url,
            confidence=0.9,
            review_status=review,
            retrieved_at=now,
        )
    )
    for aspect in supports:
        await session.execute(
            insert(knowledge_document_aspect_supports).values(
                id=uuid4(),
                document_id=document_id,
                aspect=aspect,
                support_confidence=0.95,
                review_status=ReviewStatus.auto_ingested.value,
            )
        )
    if validation_covered:
        validation_run_id = uuid4()
        await session.execute(
            insert(enrichment_validation_runs).values(
                id=validation_run_id,
                job_id=job_id,
                taxonomy_provenance_id=taxonomy_provenance_id,
                policy_version=1,
                required_aspects=[WATERING, LIGHT],
                covered_aspects=sorted(validation_covered),
                missing_aspects=[],
                answerability_status="full",
                judge_confidence=0.95,
                validation_metadata={"acquisition_avoided": False},
            )
        )
        await session.execute(
            insert(enrichment_validation_evidence).values(
                id=uuid4(),
                validation_run_id=validation_run_id,
                document_id=document_id,
            )
        )


async def test_duplicate_evidence_under_outer_transaction_converges_via_savepoint(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id: object,
) -> None:
    """With commit=False, a duplicate-evidence race must converge through a
    SAVEPOINT: the winner's document is adopted and the caller's outer
    transaction stays alive and committable."""
    from sqlalchemy import select

    from app.auth.tables import knowledge_documents

    service, session = _service(pg_session_factory, vector_index_factory)
    claim = _claim(aspects=(WATERING,))
    identity = _identity()

    # First persist commits standalone (legacy behavior).
    first = await service.persist_claim_relational(
        identity=identity,
        taxonomy_provenance_id=taxonomy_provenance_id,
        claim=claim,
        job_id=None,
    )
    assert first is not None

    # Second persistence runs inside an outer transaction with commit=False:
    # the stable content key collides, the savepoint rolls back only its own
    # writes, and convergence adopts the winner.
    second = await service.persist_claim_relational(
        identity=identity,
        taxonomy_provenance_id=taxonomy_provenance_id,
        claim=claim,
        job_id=None,
        commit=False,
    )
    assert second.document_id == first.document_id

    # The outer transaction is still usable and can be committed.
    await session.commit()

    async with pg_session_factory() as verify:
        rows = (
            await verify.execute(
                select(knowledge_documents.c.id).where(
                    knowledge_documents.c.canonical_species_key == identity.key
                )
            )
        ).all()
    assert len(rows) == 1


async def test_standalone_persistence_still_commits_without_flag(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    taxonomy_provenance_id: object,
) -> None:
    """Legacy callers without commit=False must keep their commit behavior."""
    from sqlalchemy import func, select

    from app.auth.tables import knowledge_documents

    service, _session = _service(pg_session_factory, vector_index_factory)
    state = await service.persist_claim_relational(
        identity=_identity(),
        taxonomy_provenance_id=taxonomy_provenance_id,
        claim=_claim(aspects=(WATERING,)),
        job_id=None,
    )
    await _session.close()

    async with pg_session_factory() as verify:
        count = await verify.scalar(
            select(func.count())
            .select_from(knowledge_documents)
            .where(knowledge_documents.c.id == state.document_id)
        )
    assert count == 1
