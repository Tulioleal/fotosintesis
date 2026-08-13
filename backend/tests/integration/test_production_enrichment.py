"""Production enrichment end-to-end PostgreSQL/pgvector tests.

Exercises the real `ProductionEnrichmentService.execute()` and the real
`enrich_confirmed_plant` worker handler against real repositories and
pgvector indexing, while replacing only the external provider boundaries
(search, page fetch, semantic judge, embeddings) with deterministic fakes.
"""

import asyncio
from datetime import UTC, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update

from app.auth.tables import (
    application_jobs,
    enrichment_validation_evidence,
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
)
from app.core.settings import get_settings
from app.enrichment.evidence import AcceptedEnrichmentClaim, EnrichmentEvidencePersistenceService
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.jobs.handler import HandlerRegistry
from app.jobs.handlers.enrich_confirmed_plant import EnrichConfirmedPlantHandler
from app.jobs.schemas import (
    EnrichConfirmedPlantPayload,
    JobFailureCategory,
    JobStatus,
    JobType,
)
from app.knowledge.rag import VectorIndexError
from app.knowledge.repository import KnowledgeRepository
from app.providers.errors import ProviderError

from ._enrichment_helpers import (
    LIGHT,
    PAGE_URL,
    REQUIRED,
    SAFETY_ASPECT,
    WATERING,
    DeterministicEmbeddingProvider,
    DeterministicJudgeProvider,
    DeterministicSearchProvider,
    _all_vector_node_ids,
    _aspect_supports,
    _confirmed_payload,
    _counts,
    _effect_snapshot,
    _enrichment_job,
    _page,
    _production_service,
    _providers,
    _retrieve_through_production_path,
    _schedule_via_confirmation,
    _settings,
    _taxonomy_snapshot,
    provider_environment,
    vector_index_factory,
    vector_store,
)


async def test_production_execute_acquires_persists_and_reports_terminal_coverage(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)})
    service = _production_service(pg_session_factory, _providers(judge=judge, search=search))

    execution = await service.execute(await _confirmed_payload(pg_session_factory))

    assert {aspect.value for aspect in execution.covered_aspects} == set(REQUIRED)
    assert not execution.missing_aspects
    assert execution.acquisition_avoided is False
    assert search.calls == 5

    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 17,
    }
    assert await _aspect_supports(pg_session_factory) == set(REQUIRED)

    status, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        _providers(judge=judge, search=search),
        aspect=WATERING,
    )
    assert status == "retrieved"
    assert any(
        WATERING in (chunk.metadata.get("covered_aspects") or [])
        for chunk in chunks
    )


async def test_confirmation_to_worker_executes_enrichment_and_retrieves_accepted_evidence(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()

    job_id, payload = await _schedule_via_confirmation(pg_session_factory)
    assert payload.species.normalized_binomial == "Monstera deliciosa"

    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)})
    providers = _providers(judge=judge, search=search)
    handler = EnrichConfirmedPlantHandler(
        _production_service(pg_session_factory, providers, settings=get_settings())
    )
    registry = HandlerRegistry()
    registry.register(
        JobType.enrich_confirmed_plant.value,
        handler,
        payload_models={1: EnrichConfirmedPlantPayload},
    )
    from app.jobs.worker import Worker

    worker = Worker(
        session_factory=pg_session_factory,
        handler_registry=registry,
        settings=get_settings(),
    )
    task = asyncio.create_task(worker.start())
    try:
        async with asyncio.timeout(20):
            while True:
                async with pg_session_factory() as session:
                    row = (
                        await session.execute(
                            select(
                                application_jobs.c.status,
                                application_jobs.c.result,
                            ).where(application_jobs.c.id == job_id)
                        )
                    ).mappings().one()
                if row["status"] == JobStatus.complete.value:
                    break
                await asyncio.sleep(0.05)
    finally:
        worker.stop()
        await task

    assert row["result"]["outcome"] == "complete"
    assert sorted(row["result"]["covered_aspects"]) == sorted(REQUIRED)
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 17,
    }

    status, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        providers,
        aspect=LIGHT,
    )
    assert status == "retrieved"
    assert any(
        LIGHT in (chunk.metadata.get("covered_aspects") or [])
        for chunk in chunks
    )


async def test_local_complete_evidence_avoids_search_and_records_acquisition_avoidance(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    from app.enrichment.evidence import (
        AcceptedEnrichmentClaim,
        EnrichmentEvidencePersistenceService,
    )

    identity = CanonicalSpeciesIdentity(
        accepted_gbif_key=2878688,
        normalized_binomial="Monstera deliciosa",
        taxonomy_validated=True,
    )
    taxonomy_id = await _taxonomy_snapshot(pg_session_factory)
    now = datetime(2026, 8, 1, tzinfo=UTC)
    claim = AcceptedEnrichmentClaim(
        claim="A trusted botanical source documents the required care aspects.",
        evidence_quote="Paraphrased guidance for this species.",
        source_url=PAGE_URL,
        source_title="Monstera care guide",
        source_domain="example.org",
        source_version="etag-v1",
        source_retrieved_at=now,
        source_published_at=None,
        supported_aspects=tuple(REQUIRED),
        confidence=0.95,
    )
    run_id = uuid4()
    await _enrichment_job(pg_session_factory, run_id=run_id)
    async with pg_session_factory() as session:
        repository = KnowledgeRepository(session, get_settings())
        persistence = EnrichmentEvidencePersistenceService(
            repository,
            vector_index=vector_index_factory(repository),
            embedding_provider=DeterministicEmbeddingProvider(),
        )
        state = await persistence.persist_claim_relational(
            identity=identity,
            taxonomy_provenance_id=taxonomy_id,
            claim=claim,
        )
        validation_id = await persistence.record_validation(
            job_id=run_id,
            taxonomy_provenance_id=taxonomy_id,
            policy_version=1,
            required_aspects=list(REQUIRED),
            covered_aspects=list(REQUIRED),
            missing_aspects=[],
            answerability_status="full",
            judge_confidence=0.95,
            validation_metadata={"acquisition_avoided": True},
        )
        await persistence.associate_validation_and_refresh(
            validation_id=validation_id,
            document_id=state.document_id,
        )

    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(
        pages={PAGE_URL: tuple(REQUIRED)},
        local_pages={PAGE_URL: tuple(REQUIRED)},
    )
    providers = _providers(judge=judge, search=search)
    production = _production_service(pg_session_factory, providers)
    execution = await production.execute(await _confirmed_payload(pg_session_factory))

    assert execution.acquisition_avoided is True
    assert not execution.missing_aspects
    assert search.calls == 0
    assert judge.calls == 1
    assert await _counts(pg_session_factory) == {
        "documents": 1,
        "sources": 1,
        "chunks": 1,
        "embeddings": 1,
        "supports": 17,
    }


async def test_acquired_evidence_exclusions_create_zero_knowledge_effects(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    async def run_case(
        *,
        judge: DeterministicJudgeProvider,
        fetcher_status: str | None = "trusted",
        expected_covered: set[str],
        expected_rejected: set[str],
        expect_zero_effects: bool,
    ) -> None:
        provider_environment.fetcher.validation_status = fetcher_status
        before = await _effect_snapshot(pg_session_factory, vector_store)
        search = DeterministicSearchProvider(page=_page())
        execution = await _production_service(
            pg_session_factory, _providers(judge=judge, search=search)
        ).execute(await _confirmed_payload(pg_session_factory))
        after = await _effect_snapshot(pg_session_factory, vector_store)
        covered = {aspect.value for aspect in execution.covered_aspects}
        assert covered == expected_covered
        supports = await _aspect_supports(pg_session_factory)
        assert expected_rejected.isdisjoint(supports)
        if expect_zero_effects:
            # A validation-run audit row may be created, but no evidence
            # document, association, chunk, embedding, or vector node may.
            assert after.equals_ignoring_validation_runs(before), (
                judge.pages,
                after,
                before,
            )
        else:
            assert len(after.documents) > len(before.documents)
            assert len(after.vector_node_ids) > len(before.vector_node_ids)
        provider_environment.fetcher.validation_status = "trusted"

    unknown_url_judge = DeterministicJudgeProvider(
        pages={"https://unknown.invalid/post": (WATERING,)},
        emit_unsupplied_support=True,
    )
    await run_case(
        judge=unknown_url_judge,
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )
    assert unknown_url_judge.last_result is not None
    assert WATERING in unknown_url_judge.last_result.covered_aspects
    assert any(
        support.get("source_urls") == ["https://unknown.invalid/post"]
        and WATERING in (support.get("covered_aspects") or [])
        for support in unknown_url_judge.last_result.source_support
    )

    await run_case(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
        fetcher_status=None,
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
        fetcher_status="",
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
        fetcher_status="external_fallback",
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(pages={PAGE_URL: (WATERING,)}),
        fetcher_status="rejected",
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: ()},
            malformed_support=True,
        ),
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: ()},
            include_off_request_aspect=True,
        ),
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: ()},
            include_off_registry_aspect=True,
        ),
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: (WATERING,)},
            contradiction={
                "claim_a": "Water weekly.",
                "claim_b": "Water monthly.",
                "source_a_urls": [PAGE_URL],
                "source_b_urls": [PAGE_URL],
            },
        ),
        expected_covered=set(),
        expected_rejected={WATERING},
        expect_zero_effects=True,
    )

    await run_case(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: (WATERING, SAFETY_ASPECT)},
            safety_confidence=0.80,
        ),
        expected_covered={WATERING},
        expected_rejected={SAFETY_ASPECT},
        expect_zero_effects=False,
    )
    async with pg_session_factory() as session:
        metadata_rows = (
            await session.execute(select(knowledge_chunks.c.metadata))
        ).scalars().all()
    assert all(
        SAFETY_ASPECT not in (metadata.get("covered_aspects") or [])
        for metadata in metadata_rows
    )


async def test_safety_only_low_confidence_evidence_has_zero_effects(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    """A safety-only run whose only support is below the safety threshold
    changes nothing: no documents, sources, chunks, embeddings, aspect
    supports, validation-evidence associations, or vector nodes."""
    from app.auth.tables import enrichment_validation_evidence

    provider_environment.fetcher.validation_status = "trusted"
    before = await _effect_snapshot(pg_session_factory, vector_store)
    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(
        pages={PAGE_URL: (SAFETY_ASPECT,)},
        safety_confidence=0.80,
    )
    execution = await _production_service(
        pg_session_factory, _providers(judge=judge, search=search)
    ).execute(await _confirmed_payload(pg_session_factory))
    after = await _effect_snapshot(pg_session_factory, vector_store)

    assert execution.covered_aspects == ()
    assert SAFETY_ASPECT in {item.value for item in execution.missing_aspects}
    assert execution.safety_evidence_rejected is True
    # A validation-run audit row may be recorded, but no knowledge/vector
    # effect may exist and no validation-evidence association may be created.
    assert after.equals_ignoring_validation_runs(before), (after, before)
    async with pg_session_factory() as session:
        association_count = int(
            await session.scalar(
                select(func.count()).select_from(enrichment_validation_evidence)
            )
            or 0
        )
    assert association_count == 0


async def test_provider_and_vector_failures_retry_and_converge(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(
        pages={PAGE_URL: tuple(REQUIRED)},
        fail_attempts=1,
    )
    providers = _providers(judge=judge, search=search)
    handler = EnrichConfirmedPlantHandler(
        _production_service(pg_session_factory, providers)
    )

    first = await handler.handle(
        payload=await _confirmed_payload(pg_session_factory),
        attempt_count=1,
        max_attempts=3,
    )
    assert first.status is JobStatus.failed
    assert first.error and first.error.category is JobFailureCategory.provider_transient
    assert first.error.retryable is True

    second = await handler.handle(
        payload=await _confirmed_payload(pg_session_factory),
        attempt_count=2,
        max_attempts=3,
    )
    assert second.status is JobStatus.complete
    assert await _counts(pg_session_factory) == {
        "documents": 1, "sources": 1, "chunks": 1, "embeddings": 1, "supports": 17,
    }

    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)})
    providers = _providers(judge=judge, search=search)
    handler = EnrichConfirmedPlantHandler(
        _production_service(pg_session_factory, providers)
    )
    from app.knowledge.rag.runtime import LlamaIndexRuntime as RealRuntime

    original_ensure_nodes = RealRuntime.ensure_nodes
    calls = {"n": 0}

    async def fail_once(self, **kwargs) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise VectorIndexError("transient pgvector upsert failure")
        return await original_ensure_nodes(self, **kwargs)

    monkeypatch_fixture = pytest.MonkeyPatch()
    monkeypatch_fixture.setattr(RealRuntime, "ensure_nodes", fail_once)
    try:
        first = await handler.handle(
            payload=await _confirmed_payload(pg_session_factory),
            attempt_count=1,
            max_attempts=3,
        )
    finally:
        monkeypatch_fixture.undo()
    assert first.status is JobStatus.failed
    assert first.error and first.error.category is JobFailureCategory.indexing_transient

    second = await handler.handle(
        payload=await _confirmed_payload(pg_session_factory),
        attempt_count=2,
        max_attempts=3,
    )
    assert second.status is JobStatus.complete
    assert await _counts(pg_session_factory) == {
        "documents": 1, "sources": 1, "chunks": 1, "embeddings": 1, "supports": 17,
    }


async def test_worker_lease_replacement_does_not_stale_finalize(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
    monkeypatch.setenv("JOBS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("JOBS_METRICS_PORT", "0")
    get_settings.cache_clear()

    job_id, _payload = await _schedule_via_confirmation(pg_session_factory)
    gate = asyncio.Event()
    search = DeterministicSearchProvider(page=_page())
    judge = DeterministicJudgeProvider(
        pages={PAGE_URL: tuple(REQUIRED)},
        gate=gate,
    )
    providers = _providers(judge=judge, search=search)
    from app.jobs.worker import Worker

    registry_a = HandlerRegistry()
    registry_a.register(
        JobType.enrich_confirmed_plant.value,
        EnrichConfirmedPlantHandler(
            _production_service(pg_session_factory, providers, settings=get_settings())
        ),
        payload_models={1: EnrichConfirmedPlantPayload},
    )
    worker_a = Worker(
        session_factory=pg_session_factory,
        handler_registry=registry_a,
        settings=get_settings(),
    )
    task_a = asyncio.create_task(worker_a.start())

    try:
        await asyncio.sleep(0.3)
        async with pg_session_factory() as session:
            await session.execute(
                update(application_jobs)
                .where(application_jobs.c.id == job_id)
                .values(
                    lease_owner="replacement-worker",
                    lease_token="replacement-token",
                    lease_expires_at=func.now() - text("INTERVAL '1 second'"),
                )
            )
            await session.commit()
    finally:
        gate.set()
        worker_a.stop()
        await task_a

    registry_b = HandlerRegistry()
    registry_b.register(
        JobType.enrich_confirmed_plant.value,
        EnrichConfirmedPlantHandler(
            _production_service(
                pg_session_factory,
                _providers(
                    judge=DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)}),
                    search=DeterministicSearchProvider(page=_page()),
                ),
                settings=get_settings(),
            )
        ),
        payload_models={1: EnrichConfirmedPlantPayload},
    )
    worker_b = Worker(
        session_factory=pg_session_factory,
        handler_registry=registry_b,
        settings=get_settings(),
    )
    task_b = asyncio.create_task(worker_b.start())
    try:
        async with asyncio.timeout(20):
            while True:
                async with pg_session_factory() as session:
                    row = (
                        await session.execute(
                            select(application_jobs).where(
                                application_jobs.c.id == job_id
                            )
                        )
                    ).mappings().one()
                if row["status"] == JobStatus.complete.value:
                    break
                await asyncio.sleep(0.05)
    finally:
        worker_b.stop()
        await task_b

    assert row["status"] == JobStatus.complete.value
    assert row["result"]["outcome"] == "complete"
    assert row["lease_owner"] != "replacement-worker"
    assert row["attempt_count"] == 2

    async with pg_session_factory() as session:
        from app.auth.tables import (
            candidate_enrichment_jobs,
            enrichment_validation_evidence,
            enrichment_validation_runs,
        )

        job_count = int(
            await session.scalar(
                select(func.count()).select_from(application_jobs)
            )
            or 0
        )
        association_count = int(
            await session.scalar(
                select(func.count()).select_from(candidate_enrichment_jobs)
            )
            or 0
        )
        validation_run_count = int(
            await session.scalar(
                select(func.count()).select_from(enrichment_validation_runs)
            )
            or 0
        )
        validation_evidence_count = int(
            await session.scalar(
                select(func.count()).select_from(enrichment_validation_evidence)
            )
            or 0
        )
    assert job_count == 1
    assert association_count == 1
    assert validation_run_count == 1
    assert validation_evidence_count == 1

    assert await _counts(pg_session_factory) == {
        "documents": 1, "sources": 1, "chunks": 1, "embeddings": 1, "supports": 17,
    }
    assert await _aspect_supports(pg_session_factory) == set(REQUIRED)

    async with pg_session_factory() as session:
        chunk_ids = list(
            (await session.execute(select(knowledge_chunks.c.id))).scalars().all()
        )
    relational_ids = {str(chunk_id) for chunk_id in chunk_ids}
    vector_ids = await _all_vector_node_ids(vector_store)
    assert len(relational_ids) == 1
    assert vector_ids == relational_ids
    nodes = await vector_store.aget_nodes(node_ids=[str(chunk_id) for chunk_id in chunk_ids])
    assert len(nodes) == 1
    assert sorted(nodes[0].metadata["covered_aspects"]) == sorted(REQUIRED)

    status_value, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        _providers(
            judge=DeterministicJudgeProvider(pages={PAGE_URL: tuple(REQUIRED)}),
            search=DeterministicSearchProvider(page=_page()),
        ),
        aspect=WATERING,
    )
    assert status_value == "retrieved"
    assert len(chunks) == 1


async def test_policy_expansion_reuses_unchanged_content_and_source_change_keeps_versions(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    humidity = "humidity_preference"
    search = DeterministicSearchProvider(page=_page(source_version="etag-v1"))
    judge = DeterministicJudgeProvider(
        pages={PAGE_URL: (WATERING, LIGHT)}
    )
    providers = _providers(judge=judge, search=search)
    production = _production_service(pg_session_factory, providers)

    first = await production.execute(await _confirmed_payload(pg_session_factory))
    assert {aspect.value for aspect in first.covered_aspects} == {WATERING, LIGHT}
    assert await _aspect_supports(pg_session_factory) == {WATERING, LIGHT}
    assert await _counts(pg_session_factory) == {
        "documents": 1, "sources": 1, "chunks": 1, "embeddings": 1, "supports": 2,
    }

    judge.pages = {PAGE_URL: (WATERING, LIGHT, humidity)}
    judge.local_pages = {PAGE_URL: (WATERING, LIGHT)}
    expanded = await production.execute(await _confirmed_payload(pg_session_factory))
    assert {aspect.value for aspect in expanded.covered_aspects} == {
        WATERING, LIGHT, humidity,
    }
    assert await _aspect_supports(pg_session_factory) == {WATERING, LIGHT, humidity}
    assert await _counts(pg_session_factory) == {
        "documents": 1, "sources": 1, "chunks": 1, "embeddings": 1, "supports": 3,
    }

    changed = DeterministicSearchProvider(page=_page(source_version="etag-v2"))
    providers_changed = _providers(
        judge=DeterministicJudgeProvider(
            pages={PAGE_URL: (WATERING, LIGHT, humidity)}
        ),
        search=changed,
    )
    production_changed = _production_service(pg_session_factory, providers_changed)
    changed_execution = await production_changed.execute(
        await _confirmed_payload(pg_session_factory)
    )
    assert {aspect.value for aspect in changed_execution.covered_aspects} == {
        WATERING, LIGHT, humidity,
    }
    assert await _counts(pg_session_factory) == {
        "documents": 2, "sources": 2, "chunks": 2, "embeddings": 2, "supports": 6,
    }

    status, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        providers_changed,
        aspect=LIGHT,
    )
    assert status == "retrieved"
    assert len(chunks) == 2


async def test_content_hash_and_source_version_are_independent_identity_dimensions(
    pg_session_factory,
    vector_store,
    vector_index_factory,
    provider_environment,
) -> None:
    """A change in accepted claim/quote content (same source version) must
    produce a new auditable content version, and a source-version change must
    produce a separate identity even when content is unchanged."""
    humidity = "humidity_preference"
    quote_a = DeterministicJudgeProvider(pages={PAGE_URL: (WATERING, LIGHT)})

    production = _production_service(
        pg_session_factory,
        _providers(judge=quote_a, search=DeterministicSearchProvider(page=_page(source_version="etag-v1"))),
    )
    first = await production.execute(await _confirmed_payload(pg_session_factory))
    assert {aspect.value for aspect in first.covered_aspects} == {WATERING, LIGHT}

    quote_a.pages[PAGE_URL] = (WATERING, LIGHT, humidity)
    expanded = await production.execute(await _confirmed_payload(pg_session_factory))
    assert {aspect.value for aspect in expanded.covered_aspects} == {WATERING, LIGHT, humidity}
    assert await _counts(pg_session_factory) == {
        "documents": 1, "sources": 1, "chunks": 1, "embeddings": 1, "supports": 3,
    }

    quote_b = DeterministicJudgeProvider(
        pages={PAGE_URL: (WATERING, LIGHT)},
        quote_fn=lambda aspect: f"Rewritten content B for {aspect}.",
    )
    production_b = _production_service(
        pg_session_factory,
        _providers(judge=quote_b, search=DeterministicSearchProvider(page=_page(source_version="etag-v1"))),
    )
    content_changed = await production_b.execute(await _confirmed_payload(pg_session_factory))
    assert {aspect.value for aspect in content_changed.covered_aspects} == {WATERING, LIGHT}
    assert await _counts(pg_session_factory) == {
        "documents": 2, "sources": 2, "chunks": 2, "embeddings": 2, "supports": 5,
    }

    production_v2 = _production_service(
        pg_session_factory,
        _providers(judge=quote_b, search=DeterministicSearchProvider(page=_page(source_version="etag-v2"))),
    )
    version_changed = await production_v2.execute(await _confirmed_payload(pg_session_factory))
    assert {aspect.value for aspect in version_changed.covered_aspects} == {WATERING, LIGHT}
    assert await _counts(pg_session_factory) == {
        "documents": 3, "sources": 3, "chunks": 3, "embeddings": 3, "supports": 7,
    }

    async with pg_session_factory() as session:
        rows = (
            await session.execute(
                select(
                    knowledge_documents.c.source_version,
                    knowledge_documents.c.normalized_content_hash,
                )
            )
        ).all()
    versions = [str(row[0]) for row in rows]
    hashes = [str(row[1]) for row in rows]
    assert sorted(versions) == ["etag-v1", "etag-v1", "etag-v2"]
    # The content hash reflects only the accepted claim/quote content: the
    # two quote-A/quote-B documents have distinct hashes, while the version
    # change preserves the quote-B hash but yields a distinct content identity.
    assert len(set(hashes)) == 2
    assert len({(version, hash_value) for version, hash_value in zip(versions, hashes, strict=True)}) == 3

    status_value, chunks = await _retrieve_through_production_path(
        pg_session_factory,
        vector_index_factory,
        _providers(judge=quote_b, search=DeterministicSearchProvider(page=_page())),
        aspect=WATERING,
    )
    assert status_value == "retrieved"
    assert len(chunks) == 3
