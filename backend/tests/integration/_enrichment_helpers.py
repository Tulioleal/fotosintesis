"""Shared deterministic provider-boundary fixtures for enrichment tests.

These helpers replace only the external provider boundaries (search, page
fetch, semantic judge, embeddings) with deterministic fakes while retaining
the real production orchestration, repositories, and pgvector indexing.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.engine import make_url

from app.auth.tables import (
    application_jobs,
    enrichment_validation_evidence,
    enrichment_validation_runs,
    identification_candidates,
    identification_images,
    knowledge_chunks,
    knowledge_document_aspect_supports,
    knowledge_documents,
    knowledge_embeddings,
    knowledge_sources,
    taxonomy_provenance_snapshots,
    users,
)
from app.core.settings import Settings, get_settings
from app.enrichment.identity import CanonicalSpeciesIdentity
from app.enrichment.policy import ENRICHMENT_POLICY_V1
from app.enrichment.service import ProductionEnrichmentService
from app.identification.confirmation import CandidateConfirmationService
from app.jobs.schemas import EnrichConfirmedPlantPayload
from app.knowledge.acquisition import KnowledgeAcquisitionService, TrustedSourceValidator
from app.knowledge.page_evidence import TrustedPageEvidence
from app.knowledge.rag import KnowledgeVectorIndex, LlamaIndexRuntime
from app.knowledge.repository import KnowledgeRepository
from app.providers.errors import ProviderError
from app.providers.types import EmbeddingResult, JudgeResult, SearchResult

from .conftest import BASE_DATABASE_URL

PAGE_URL = "https://example.org/monstera-care"
WATERING = "watering_frequency_or_trigger"
LIGHT = "light_exposure"
SAFETY_ASPECT = "toxicity_pet_safety"
SPECIES_KEY = "gbif:2878688|binomial:Monstera deliciosa"
SPECIES_NAME = "Monstera deliciosa"
REQUIRED = tuple(
    aspect.value for aspect in ENRICHMENT_POLICY_V1.required_aspects
)
SAFETY = tuple(
    aspect.value for aspect in ENRICHMENT_POLICY_V1.safety_sensitive_aspects
)


class DeterministicEmbeddingProvider:
    async def create_embeddings(self, texts: list[str], **kwargs) -> EmbeddingResult:
        return EmbeddingResult(
            provider="deterministic",
            model="deterministic-8d",
            embeddings=[[0.1] * 8 for _ in texts],
        )


class DeterministicSearchProvider:
    def __init__(self, *, page: SearchResult | None = None) -> None:
        self.page = page
        self.calls = 0

    async def search(self, query: str, **kwargs) -> list[SearchResult]:
        self.calls += 1
        return [self.page] if self.page else []


class DeterministicPageFetcher:
    def __init__(
        self,
        *,
        content: str,
        validation_status: str = "trusted",
    ) -> None:
        self.content = content
        self.validation_status = validation_status

    async def fetch_all(self, results, *, limit=3) -> list[TrustedPageEvidence]:
        return [
            TrustedPageEvidence(
                result=result,
                content=self.content,
                validation_status=self.validation_status,
                fetch_status="fetched",
            )
            for result in results[:limit]
        ]


class DeterministicJudgeProvider:
    """Scripted semantic judge at the provider boundary.

    ``pages`` maps a source URL to the canonical aspects the judge supports
    when that URL is present in the supplied source metadata. ``local_pages``
    applies to local (non-final) judging calls. All aspects of one URL are
    emitted as a single source-support item with a paraphrased quote that is
    not literally present in the evidence text.
    """

    def __init__(
        self,
        *,
        pages: dict[str, tuple[str, ...]] | None = None,
        local_pages: dict[str, tuple[str, ...]] | None = None,
        safety_confidence: float = 0.95,
        contradiction: dict[str, object] | None = None,
        gate: asyncio.Event | None = None,
        fail_attempts: int = 0,
        quote_fn=None,
        malformed_support: bool = False,
        include_off_registry_aspect: bool = False,
        include_off_request_aspect: bool = False,
        emit_unsupplied_support: bool = False,
    ) -> None:
        self.pages = pages or {}
        self.local_pages = local_pages
        self.safety_confidence = safety_confidence
        self.contradiction = contradiction
        self.gate = gate
        self.fail_attempts = fail_attempts
        self.quote_fn = quote_fn or (
            lambda aspect: (
                f"Paraphrased {aspect} guidance that is not an exact substring "
                "of the supplied evidence text."
            )
        )
        self.malformed_support = malformed_support
        self.include_off_registry_aspect = include_off_registry_aspect
        self.include_off_request_aspect = include_off_request_aspect
        self.emit_unsupplied_support = emit_unsupplied_support
        self.calls = 0
        self.last_result: JudgeResult | None = None

    async def judge_response(self, payload: dict, rubric: dict, **kwargs) -> JudgeResult:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.fail_attempts and self.calls <= self.fail_attempts:
            raise ProviderError("deterministic judge unavailable")
        requested = list(payload.get("required_aspects") or [])
        raw_sources = (
            payload.get("evidence_sources")
            if payload.get("evidence_sources") is not None
            else payload.get("source_metadata")
        )
        urls = {
            str(metadata.get("url"))
            for metadata in raw_sources or []
            if isinstance(metadata, dict) and metadata.get("url")
        }
        pages = (
            self.local_pages if payload.get("local_answerability") is None else self.pages
        ) or {}
        if self.contradiction is not None:
            result = JudgeResult(
                provider="deterministic",
                score=0.0,
                passed=False,
                status="contradictory",
                covered_aspects=[],
                missing_aspects=requested,
                contradictions=[self.contradiction],
                confidence=0.9,
            )
            self.last_result = result
            return result
        covered: list[str] = []
        support: list[dict[str, object]] = []
        for url, aspects in pages.items():
            if url not in urls and not self.emit_unsupplied_support:
                continue
            accepted = [aspect for aspect in aspects if aspect in requested]
            for aspect in accepted:
                if aspect not in covered:
                    covered.append(aspect)
            if accepted:
                support.append(
                    {
                        "claim": (
                            "A trusted botanical source documents the required "
                            "botanical care guidance for this species."
                        ),
                        "evidence_quote": self.quote_fn(accepted[0]),
                        "source_urls": [url],
                        "covered_aspects": accepted,
                        "confidence": (
                            self.safety_confidence
                            if any(aspect in SAFETY for aspect in accepted)
                            else 0.95
                        ),
                    }
                )
        if self.malformed_support and urls:
            support.append(
                {
                    "claim": "",
                    "evidence_quote": "",
                    "source_urls": [],
                    "covered_aspects": [],
                    "confidence": 0.95,
                }
            )
        if self.include_off_registry_aspect and urls:
            support.append(
                {
                    "claim": "Off-registry claim.",
                    "evidence_quote": "Off-registry quote.",
                    "source_urls": [next(iter(urls))],
                    "covered_aspects": ["off_registry_aspect"],
                    "confidence": 0.95,
                }
            )
        if self.include_off_request_aspect and urls:
            support.append(
                {
                    "claim": "Off-request claim.",
                    "evidence_quote": "Off-request quote.",
                    "source_urls": [next(iter(urls))],
                    "covered_aspects": ["toxicity_ingestion_symptoms"],
                    "confidence": 0.95,
                }
            )
        status = "full" if set(covered) == set(requested) else (
            "partial" if covered else "insufficient"
        )
        result = JudgeResult(
            provider="deterministic",
            score=0.9,
            passed=status == "full",
            status=status,
            covered_aspects=covered,
            missing_aspects=[aspect for aspect in requested if aspect not in covered],
            source_support=support,
            confidence=0.95,
        )
        self.last_result = result
        return result


def _settings(**overrides) -> Settings:
    return Settings(
        jobs_producer_enabled=True,
        jobs_worker_enabled=True,
        jobs_poll_interval_seconds=0.05,
        jobs_lease_duration_seconds=30.0,
        jobs_lease_renewal_interval_seconds=0.05,
        jobs_backoff_base_seconds=0.05,
        jobs_metrics_port=0,
        trusted_source_domains=["example.org"],
        **overrides,
    )


def _page(
    *,
    url: str = PAGE_URL,
    source_version: str = "etag-v1",
    snippet: str = "Trusted botanical page content about Monstera deliciosa.",
) -> SearchResult:
    return SearchResult(
        title="Monstera care guide",
        url=url,
        snippet=snippet,
        source_domain="example.org",
        metadata={"source_version": source_version},
    )


def _providers(
    *,
    judge: DeterministicJudgeProvider,
    search: DeterministicSearchProvider,
) -> SimpleNamespace:
    return SimpleNamespace(
        judge=judge,
        search=search,
        embeddings=DeterministicEmbeddingProvider(),
    )


def _production_service(
    pg_session_factory,
    providers,
    settings: Settings | None = None,
    *,
    policy_resolver=None,
    vector_index_factory=None,
) -> ProductionEnrichmentService:
    kwargs: dict[str, object] = {}
    if policy_resolver is not None:
        kwargs["policy_resolver"] = policy_resolver
    if vector_index_factory is not None:
        kwargs["vector_index_factory"] = vector_index_factory
    return ProductionEnrichmentService(
        session_factory=pg_session_factory,
        providers=providers,
        settings=settings or _settings(),
        **kwargs,
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
        table_name="enrichment_efficacy",
        schema_name=pg_schema,
        embed_dim=8,
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


@pytest.fixture
def provider_environment(monkeypatch, vector_store):
    """Point every production provider boundary at deterministic fixtures."""

    from app.enrichment import acquisition as acquisition_module
    from app.enrichment import service as enrichment_service_module
    from app.knowledge.rag import runtime as runtime_module

    monkeypatch.setattr(
        runtime_module, "create_llamaindex_pgvector_store", lambda settings: vector_store
    )
    monkeypatch.setattr(
        enrichment_service_module,
        "TrustedSourceValidator",
        lambda: TrustedSourceValidator(["example.org"]),
    )
    fetcher = DeterministicPageFetcher(
        content="Trusted botanical page content about Monstera deliciosa."
    )
    monkeypatch.setattr(
        acquisition_module,
        "TrustedPageEvidenceFetcher",
        lambda trusted_sources: fetcher,
    )
    return SimpleNamespace(fetcher=fetcher)


async def _taxonomy_snapshot(pg_session_factory) -> UUID:
    provenance_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            insert(taxonomy_provenance_snapshots).values(
                id=provenance_id,
                canonical_species_key=SPECIES_KEY,
                accepted_gbif_key=2878688,
                normalized_binomial=SPECIES_NAME,
                taxonomy_source="gbif",
                taxonomy_source_version=f"fixture-{uuid4().hex[:8]}",
                snapshot={"accepted": True},
                resolved_at=datetime(2026, 8, 1, tzinfo=UTC),
            )
        )
        await session.commit()
    return provenance_id


async def _enrichment_job(
    pg_session_factory, *, run_id: UUID, policy_version: int = 1
) -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    async with pg_session_factory() as session:
        await session.execute(
            insert(application_jobs).values(
                id=run_id,
                job_type="enrich_confirmed_plant",
                payload_version=1,
                payload={
                    "run_id": str(run_id),
                    "policy_version": policy_version,
                },
                status="processing",
                idempotency_key=f"production-enrichment-{uuid4()}",
                attempt_count=1,
                max_attempts=3,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _confirmed_payload(
    pg_session_factory, *, policy_version: int = 1
) -> EnrichConfirmedPlantPayload:
    taxonomy_id = await _taxonomy_snapshot(pg_session_factory)
    run_id = uuid4()
    await _enrichment_job(
        pg_session_factory, run_id=run_id, policy_version=policy_version
    )
    return EnrichConfirmedPlantPayload.model_validate(
        {
            "payload_version": 1,
            "policy_version": policy_version,
            "species": {
                "accepted_gbif_key": 2878688,
                "normalized_binomial": SPECIES_NAME,
            },
            "taxonomy_provenance_id": str(taxonomy_id),
            "run_id": str(run_id),
        }
    )


async def _all_vector_node_ids(vector_store) -> set[str]:
    """Return every node ID present in the vector store table.

    This is test-only code that uses the vector store's private table
    metadata so it can detect orphan nodes and unexpected IDs; the public
    ``aget_nodes(node_ids=...)`` API cannot observe nodes it does not query.
    """
    vector_store._initialize()
    async with vector_store._async_engine.connect() as connection:
        rows = (
            await connection.execute(select(vector_store._table_class.node_id))
        ).scalars().all()
    return {str(row) for row in rows}


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


async def _aspect_supports(session_factory) -> set[str]:
    async with session_factory() as session:
        return set(
            (
                await session.execute(
                    select(knowledge_document_aspect_supports.c.aspect)
                )
            ).scalars().all()
        )


@dataclass
class EffectSnapshot:
    """Complete relational and vector effects after an enrichment run.

    Captures only stable identities and authoritative aspect mappings (not
    every mutable database column): document/source/chunk/embedding IDs,
    (document_id, aspect) support pairs, validation-evidence association
    pairs, validation-run IDs, relational support aspects per document, chunk
    document IDs and relationally refreshed chunk metadata aspects, and every
    vector node's metadata aspects.
    """

    documents: set[UUID] = field(default_factory=set)
    sources: set[UUID] = field(default_factory=set)
    chunks: set[UUID] = field(default_factory=set)
    embeddings: set[UUID] = field(default_factory=set)
    supports: set[tuple[UUID, str]] = field(default_factory=set)
    validation_evidence: set[tuple[UUID, UUID]] = field(default_factory=set)
    validation_run_ids: set[UUID] = field(default_factory=set)
    vector_node_ids: set[str] = field(default_factory=set)
    relational_chunk_ids: set[str] = field(default_factory=set)
    relational_aspects_by_document: dict[str, frozenset[str]] = field(
        default_factory=dict
    )
    chunk_document_ids: dict[str, str] = field(default_factory=dict)
    chunk_aspects: dict[str, frozenset[str]] = field(default_factory=dict)
    vector_aspects: dict[str, frozenset[str]] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "documents": len(self.documents),
            "sources": len(self.sources),
            "chunks": len(self.chunks),
            "embeddings": len(self.embeddings),
            "supports": len(self.supports),
            "validation_evidence": len(self.validation_evidence),
            "vector_node_ids": len(self.vector_node_ids),
            "relational_chunk_ids": len(self.relational_chunk_ids),
        }

    def delta(self, other: "EffectSnapshot") -> "EffectSnapshot":
        return EffectSnapshot(
            documents=self.documents - other.documents,
            sources=self.sources - other.sources,
            chunks=self.chunks - other.chunks,
            embeddings=self.embeddings - other.embeddings,
            supports=self.supports - other.supports,
            validation_evidence=self.validation_evidence - other.validation_evidence,
            vector_node_ids=self.vector_node_ids - other.vector_node_ids,
            relational_chunk_ids=self.relational_chunk_ids - other.relational_chunk_ids,
        )

    def equals_ignoring_validation_runs(self, other: "EffectSnapshot") -> bool:
        """Compare every effect except validation-run audit IDs.

        A validation-run audit row is legitimately recorded for executions
        that persist no evidence, so zero-effect comparisons must ignore that
        single audit dimension while comparing every knowledge/vector effect.
        """
        for field_name in (
            "documents",
            "sources",
            "chunks",
            "embeddings",
            "supports",
            "validation_evidence",
            "vector_node_ids",
            "relational_chunk_ids",
            "relational_aspects_by_document",
            "chunk_document_ids",
            "chunk_aspects",
            "vector_aspects",
        ):
            if getattr(self, field_name) != getattr(other, field_name):
                return False
        return True

    def assert_relational_vector_convergence(self) -> None:
        """Relational, chunk-metadata, and vector-metadata aspect state agree.

        Asserts vector node IDs equal relational chunk IDs (one node per chunk
        and one chunk per node), and that for every chunk the relational
        document support equals both the relationally refreshed chunk metadata
        aspects and the vector node metadata aspects, so no aspect exists only
        in one layer and none is missing from another.
        """
        assert self.vector_node_ids == self.relational_chunk_ids, self
        assert set(self.chunk_document_ids) == self.relational_chunk_ids, self
        assert set(self.vector_aspects) == self.relational_chunk_ids, self
        for chunk_id in self.relational_chunk_ids:
            document_id = self.chunk_document_ids[chunk_id]
            relational = self.relational_aspects_by_document.get(
                document_id, frozenset()
            )
            chunk_aspects = self.chunk_aspects[chunk_id]
            vector_aspects = self.vector_aspects[chunk_id]
            assert chunk_aspects == relational, (
                chunk_id,
                "chunk metadata diverges from relational support",
                chunk_aspects,
                relational,
            )
            assert vector_aspects == relational, (
                chunk_id,
                "vector metadata diverges from relational support",
                vector_aspects,
                relational,
            )


async def _all_vector_nodes(vector_store) -> dict[str, frozenset[str]]:
    """Return every vector-table node's metadata ``covered_aspects``.

    Queries every node ID in the vector store table and then loads each node
    through ``aget_nodes`` so orphan or unexpected nodes are also observed.
    """
    vector_store._initialize()
    async with vector_store._async_engine.connect() as connection:
        rows = (
            await connection.execute(select(vector_store._table_class.node_id))
        ).scalars().all()
    node_ids = sorted({str(row) for row in rows})
    if not node_ids:
        return {}
    nodes = await vector_store.aget_nodes(node_ids=node_ids)
    result: dict[str, frozenset[str]] = {}
    for node in nodes:
        metadata = node.metadata or {}
        result[node.node_id] = frozenset(metadata.get("covered_aspects") or [])
    return result


async def _effect_snapshot(pg_session_factory, vector_store) -> EffectSnapshot:
    async with pg_session_factory() as session:
        documents = set(
            (await session.execute(select(knowledge_documents.c.id))).scalars().all()
        )
        sources = set(
            (await session.execute(select(knowledge_sources.c.id))).scalars().all()
        )
        chunks = set(
            (await session.execute(select(knowledge_chunks.c.id))).scalars().all()
        )
        embeddings = set(
            (await session.execute(select(knowledge_embeddings.c.id))).scalars().all()
        )
        supports = set(
            (
                await session.execute(
                    select(
                        knowledge_document_aspect_supports.c.document_id,
                        knowledge_document_aspect_supports.c.aspect,
                    )
                )
            ).all()
        )
        validation_evidence = set(
            (
                await session.execute(
                    select(
                        enrichment_validation_evidence.c.validation_run_id,
                        enrichment_validation_evidence.c.document_id,
                    )
                )
            ).all()
        )
        validation_run_ids = set(
            (
                await session.execute(
                    select(enrichment_validation_runs.c.id)
                )
            ).scalars().all()
        )
        chunk_rows = (
            await session.execute(
                select(
                    knowledge_chunks.c.id,
                    knowledge_chunks.c.document_id,
                    knowledge_chunks.c.metadata,
                )
            )
        ).all()
    relational_aspects_by_document: dict[str, set[str]] = {}
    for document_id, aspect in supports:
        relational_aspects_by_document.setdefault(str(document_id), set()).add(
            aspect
        )
    chunk_document_ids: dict[str, str] = {}
    chunk_aspects: dict[str, frozenset[str]] = {}
    for chunk_id, document_id, metadata in chunk_rows:
        chunk_document_ids[str(chunk_id)] = str(document_id)
        chunk_aspects[str(chunk_id)] = frozenset(
            (metadata or {}).get("covered_aspects") or []
        )
    return EffectSnapshot(
        documents=documents,
        sources=sources,
        chunks=chunks,
        embeddings=embeddings,
        supports={(document_id, aspect) for document_id, aspect in supports},
        validation_evidence={
            (validation_run_id, document_id)
            for validation_run_id, document_id in validation_evidence
        },
        validation_run_ids=validation_run_ids,
        vector_node_ids=await _all_vector_node_ids(vector_store),
        relational_chunk_ids={str(chunk_id) for chunk_id in chunks},
        relational_aspects_by_document={
            key: frozenset(values)
            for key, values in relational_aspects_by_document.items()
        },
        chunk_document_ids=chunk_document_ids,
        chunk_aspects=chunk_aspects,
        vector_aspects=await _all_vector_nodes(vector_store),
    )


async def _document_content_keys(session_factory) -> set[tuple[str, str, str]]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    knowledge_documents.c.canonical_source_url,
                    knowledge_documents.c.source_version,
                    knowledge_documents.c.normalized_content_hash,
                )
            )
        ).all()
        return {
            (str(row[0]), str(row[1]), str(row[2])) for row in rows
        }


async def _retrieve_through_production_path(
    pg_session_factory,
    vector_index_factory,
    providers,
    *,
    aspect: str,
) -> list:
    async with pg_session_factory() as session:
        repository = KnowledgeRepository(session, get_settings())
        service = KnowledgeAcquisitionService(
            repository,
            providers=SimpleNamespace(
                model=providers.judge,
                search=providers.search,
                embeddings=providers.embeddings,
            ),
            trusted_sources=TrustedSourceValidator(["example.org"]),
            vector_index=vector_index_factory(repository),
        )
        result = await service.retrieve_or_acquire(
            scientific_name=SPECIES_NAME,
            topic="confirmed_plant_enrichment",
            canonical_species_key=SPECIES_KEY,
            accepted_gbif_key=2878688,
            required_aspects=[aspect],
            question=aspect,
        )
        return result.status.value, result.chunks


async def _schedule_via_confirmation(pg_session_factory):
    user_id = uuid4()
    identification_id = uuid4()
    candidate_id = uuid4()
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
                message="Confirm.",
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
            )
        )
        await session.commit()

        response = await CandidateConfirmationService(
            session, _settings()
        ).confirm(
            identification_id=identification_id,
            candidate_id=candidate_id,
            user_id=user_id,
        )
        job_id = response.enrichment.job.id
        payload = EnrichConfirmedPlantPayload.model_validate(
            (
                await session.execute(
                    select(application_jobs.c.payload).where(
                        application_jobs.c.id == job_id
                    )
                )
            ).scalar_one()
        )
    return job_id, payload
